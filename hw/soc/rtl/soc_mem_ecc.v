// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The memory codec and the scrubber: what stands between the fabric and
// a row of storage, in ONE file for both memory implementations.
//
// hw/soc/rtl/soc_mem.v (the behavioural array) and hw/soc/rtl/
// soc_mem_sram.v (the RM_IHPSG13 macros) both instantiate this module
// at HARDEN = 1, so the code, the write masks, the read-path correction,
// the error response and the scrubber exist ONCE and are verified once.
// What differs between the two files is only what sits on the row port
// below: a register array or six vendor macros and a bank multiplexer.
//
// =====================================================================
// THE ROW, AND WHY ONE WORD PER ROW
// =====================================================================
//
// docs/47 section 4 chose RM_IHPSG13_1P_2048x64_c2_bm_bist for the RAM,
// a 64-bit row, and held two 32-bit words in each row. That is the
// densest byte-writable arrangement the library offers and it leaves
// NO bit for a check field: (72,64) needs eight more than the row has,
// and (39,32) per word needs fourteen. docs/67 section 3 costs every
// way out -- a seventh macro for the check bits, a different code, a
// narrower word -- and this file is the one it chose:
//
//   ONE 32-bit word per 64-bit row, held as FOUR (16,8) codewords, one
//   per byte lane:
//
//       row[63:56] check bits of byte 3     row[31:24] byte 3
//       row[55:48] check bits of byte 2     row[23:16] byte 2
//       row[47:40] check bits of byte 1     row[15: 8] byte 1
//       row[39:32] check bits of byte 0     row[ 7: 0] byte 0
//
// Each (16,8) codeword is the SHORTENING of the one SECDED code this
// repository owns -- hw/rtl/secded_enc.v and secded_dec.v, (72,64),
// proved in formal/secded.sby -- with data bits 8..63 tied to zero, the
// same construction hw/soc/rtl/ibex_regfile_secded.v uses to make a
// (40,32) out of it. Over eight data bits three of the eight check rows
// are identically zero (H_ROW5, H_ROW6 and H_ROW7 have no bit set below
// bit 8), so what is stored is a (13,8) code plus three constant-zero
// bits, which is the MINIMAL SECDED width for a byte; the three spare
// bits cost nothing because the row has them anyway.
// hw/soc/formal/byte_secded.sby proves the shortening.
//
// WHY BYTES AND NOT A WORD CODE. Ibex emits sb and sh, and soc_bus.v's
// contract carries be_i[3:0]. A code over a wider field than the write
// granularity forces a read-modify-write on every narrower store, which
// is the protocol change docs/47 section 4.2 refused when it struck the
// 8192x32 part out for having no bit mask. A code per BYTE is written
// byte by byte through the macro's own A_BM, so there is no
// read-modify-write, no cycle, no change to gnt_o = req_i and nothing
// for soc_bus.v to re-prove. It is also a shallower decoder than the
// 64-bit one on a read path docs/50 measured as the design's binding
// path -- docs/67 section 5 measures it.
//
// THE COST IS HALF THE RAM. 64 KiB of macro holds 32 KiB of protected
// words. regmap/memmap.yaml says 32 KiB and docs/67 section 3 says why
// the 32 KiB that went were the 32 KiB nothing uses.
//
// THE ROM IS A WORD CODE. RO = 1 memories are never written by the bus,
// so the read-modify-write argument does not apply, and the ROM's
// macros are 32 bits wide with no spare bit at all: its seven check
// bits -- the (39,32) shortening ibex_regfile_secded.v already proves --
// go in a separate, narrower macro, and ECC_BYTE = 0 selects that
// layout: row[38:32] is the check field and row[31:0] the word. The
// elaboration guard below refuses ECC_BYTE = 0 on a writable memory.
//
// =====================================================================
// CORRECT ON READ, TRAP ON UNCORRECTABLE, SCRUB IN THE GAPS
// =====================================================================
//
// Every read decodes the row on the way out; a single-bit error in any
// byte codeword is corrected before rdata_o and the read reports it on
// rd_o. An UNCORRECTABLE syndrome answers the read with err_o, which
// the fabric carries to the core as a load, store or instruction access
// fault -- the recovery is a trap, not a wrong word, and soc_bus.v rule
// 3 already carries err in the response cycle. A double error is
// detected and never miscorrected, which is what the odd column weights
// of the code buy (secded_dec.v's header).
//
// THE SCRUBBER IS A BACK-DOOR ON THIS PORT AND NOT A FABRIC MASTER.
// docs/51 section 12 priced a third bus master as a re-proof of the
// fabric; this needs none. Every cycle in which the bus is not asking
// for the row port and the interval counter has expired, the scrubber
// reads one row; on the next cycle -- if the bus is still idle -- it
// writes back every byte lane the decoder corrected, re-encoded, and
// advances. If the bus takes the port on that second cycle the result
// is dropped and the row is visited again later: the bus always wins,
// nothing is ever withheld from it, and a bus write that lands between
// the scrub read and its write-back cannot be overwritten, because the
// write-back does not happen. sec_o is raised once per row REPAIRED,
// which is what makes it the upset-rate counter the way
// BUSSTAT.CNT_RFSEC is the register file's; rd_o is raised per read
// that returned a corrected word, which is the CNT_RFRD shape and
// deliberately not the same number.
//
// A lane the decoder reports uncorrectable is NEVER written back. Re-
// encoding a wrong word would launder the error into a valid codeword
// over a wrong value -- the failure soc_clint.v H6 calls "the standard
// way to build an ECC counter that silently does nothing" -- so the
// lane is left as it is, counted on ded_o with its address, and the
// next bus read of it traps.
//
// The interval is scrub_ivl_i idle cycles between scrub reads, with a
// floor of two because the row read in one cycle is examined in the
// next; at 0 or 1 the scrubber reads on every second idle cycle.
// hw/soc/rtl/soc_scrub.v owns the register that sets it and the counters
// the three event lines feed.
//
// =====================================================================
// THE DECODER'S SYNDROME IS USED AND ITS OUTPUTS ARE NOT, AND WHY
// =====================================================================
//
// hw/rtl/secded_dec.v computes its correction by matching the syndrome
// against ALL 64 data columns of H and OR-ing the 64 matches into
// `data_hit`, then qualifying with an eight-bit subtract for the
// check-bit case. Over a byte codeword 56 of those columns belong to
// bits that are tied to zero, and the synthesiser cannot remove a
// comparison whose result feeds `data_hit` -- so the shortened decoder
// would carry the full (72,64) match on a path that ends at a macro's
// A_BM pin with a 2.2 ns library setup, and docs/67 section 5 measured
// it there, on the worst path into a macro.
//
// So this file does what hw/soc/rtl/ibex_regfile_secded.v's FASTCORR
// does, one step further. The frozen decoder is instantiated for its
// SYNDROME -- the eight XOR trees over the received word -- and nothing
// else; the correction mask is the syndrome compared against the H
// columns of the bits the codeword actually stores, derived from the
// frozen encoder on unit vectors exactly as the register file derives
// them, and the two flags follow:
//
//     mask[b]  = (syndrome == column of live data bit b)
//     sec      = |mask  ||  syndrome is a single set bit  (a check bit)
//     ded      = syndrome != 0  &&  !sec
//     data     = raw ^ mask
//
// For every error of weight 0, 1 or 2 -- the whole SEC-DED guarantee --
// data, sec and ded are BIT FOR BIT the frozen decoder's, and
// hw/soc/formal/byte_secded.sby B6 and regfile_secded.sby C8 state the
// equality over a free codeword and a free error vector rather than
// take this paragraph's word for it. Where the two differ is weight
// three and above, and the difference is in this file's favour: a
// triple error whose syndrome happens to equal a TIED-OFF column makes
// the frozen decoder report `sec` and "correct" a bit that is not
// stored, which is a wrong word delivered as corrected; here the same
// syndrome matches no live column and is reported uncorrectable, which
// is what the (13,8) code's own decoder would say. The cover in
// byte_secded.sby that reaches that case is the record that the two
// behaviours were compared and this one chosen.
//
// =====================================================================
// WHAT THIS FILE DOES NOT PROTECT
// =====================================================================
//
//   * THE ADDRESS. A corrupted row index reads or writes the wrong row,
//     which is a perfectly valid codeword; the same limit
//     ibex_regfile_secded.v states for its read addresses.
//   * The response registers, the bank and lane selects in the wrapper,
//     and the scrubber's own pointer: an upset in the pointer moves
//     where the next scrub read lands and nothing else.
//   * The codec itself. A single-event transient inside an encoder or a
//     decoder is a fault model no campaign in this repository can
//     express (docs/58 section 11).
//   * A second upset in the SAME 16-bit codeword before the scrubber
//     or a read reaches the first: detected, not corrected, and docs/67
//     section 6 bounds the window.

`timescale 1ns / 1ps

module soc_mem_ecc #(
    parameter integer WORDS    = 8192,
    parameter         RO       = 1'b0,
    parameter integer HARDEN   = 1,
    // 1: four (16,8) byte codewords in a 64-bit row (the RAM).
    // 0: one (39,32) word codeword in a 39-bit row (the ROM), RO only.
    parameter         ECC_BYTE = 1'b1,
    // docs/50's response register. See soc_mem.v.
    parameter         RDREG    = 1'b0,
    // Row width: 64 with byte codes, 39 with the word code. A parameter
    // rather than a derived constant so that the port widths are plain
    // in the instantiating file.
    parameter integer RW       = 64
) (
    input  wire        clk_i,
    input  wire        rst_ni,

    // ---- the fabric slave port, soc_mem's ----
    input  wire        req_i,
    input  wire [31:0] addr_i,
    input  wire        we_i,
    input  wire [3:0]  be_i,
    input  wire [31:0] wdata_i,
    output wire        gnt_o,
    output wire        rvalid_o,
    output wire [31:0] rdata_o,
    output wire        err_o,

    // ---- the row port: the shape of one RM_IHPSG13 macro ----
    // One access per cycle. A read presents the row on row_dout_i in
    // the NEXT cycle and row_dout_i then holds until the next read; a
    // write lands at the edge and changes row_dout_i not at all. That
    // is SRAM_1P_behavioral_bm_bist's behaviour and soc_mem.v's array
    // reproduces it.
    output wire                     row_en_o,
    output wire                     row_we_o,
    output wire [$clog2(WORDS)-1:0] row_addr_o,
    output wire [RW-1:0]            row_din_o,
    output wire [RW-1:0]            row_bm_o,    // 1 = write this bit
    input  wire [RW-1:0]            row_dout_i,

    // ---- the scrubber's control, from soc_scrub.v ----
    input  wire        scrub_en_i,
    input  wire [15:0] scrub_ivl_i,

    // ---- the reports, one cycle per event ----
    output wire        sec_o,       // a row the scrubber REPAIRED
    output wire        rd_o,        // a read that returned a corrected word
    output wire        ded_o,       // an uncorrectable row, on read or scrub
    output wire [31:0] evt_addr_o   // byte offset of that row, with ded_o
);

  localparam integer AW = $clog2(WORDS);
  localparam integer CW = RW - 32;

  // Elaboration guards, aer_fifo house style: a configuration this file
  // has no meaning for references a module that does not exist.
  generate
    if (RW != (ECC_BYTE ? 64 : 39)) begin : g_bad_row
      ERROR_soc_mem_ecc_row_width_does_not_match_the_code guard ();
    end
    if (!ECC_BYTE && !RO) begin : g_bad_word_code
      // A word code over a byte-writable memory is a read-modify-write
      // on every sb and sh. Not built; see the header.
      ERROR_soc_mem_ecc_word_code_needs_a_read_only_memory guard ();
    end
    if (WORDS < 2 || (WORDS & (WORDS - 1)) != 0) begin : g_bad_words
      ERROR_soc_mem_ecc_words_must_be_a_power_of_two guard ();
    end
  endgenerate

  // Always ready. The scrubber never withholds the port from the bus.
  assign gnt_o = req_i;

  wire write_attempt = req_i && we_i;
  wire do_write      = write_attempt && !RO;
  wire [AW-1:0] bus_row = addr_i[AW+1:2];

  // ---- the read path ------------------------------------------------
  //
  // The decoders sit on row_dout_i unconditionally: whatever the row
  // port last read is decoded every cycle, and the response logic and
  // the scrubber each take the result in the cycle that is theirs.
  wire [31:0] rd_word;        // corrected (HARDEN) or raw
  wire [3:0]  sec;            // per lane; [0] only for the word code
  wire [3:0]  ded;

  // The H columns of the live data bits, derived from the frozen encoder
  // on unit vectors (ibex_regfile_secded.v's argument for deriving and
  // not writing them down): a compile-time table the synthesiser folds.
  localparam integer NCOL = ECC_BYTE ? 8 : 32;
  wire [7:0] h_col [0:NCOL-1];
  genvar gc;
  generate
    for (gc = 0; gc < NCOL; gc = gc + 1) begin : g_col
      wire [71:0] col_code_unused;
      secded_enc u_col (
          .data_in   ({{(64-NCOL){1'b0}}, {{(NCOL-1){1'b0}}, 1'b1} << gc}),
          .check_out (h_col[gc]),
          .code_out  (col_code_unused)
      );
    end
  endgenerate

  generate
    if (HARDEN && ECC_BYTE) begin : g_dec_byte
      genvar l, b;
      for (l = 0; l < 4; l = l + 1) begin : g_lane
        wire [63:0] d64_unused;
        wire [7:0]  syn;
        wire        sec_dec_unused, ded_dec_unused;
        secded_dec u_dec (
            .code_in  ({row_dout_i[32+8*l +: 8], 56'h0, row_dout_i[8*l +: 8]}),
            .data_out (d64_unused),
            .syndrome (syn),
            .sec      (sec_dec_unused),
            .ded      (ded_dec_unused)
        );
        wire [7:0] mask;
        for (b = 0; b < 8; b = b + 1) begin : g_bit
          assign mask[b] = (syn == h_col[b]);
        end
        wire syn_nz  = |syn;
        wire onehot  = syn_nz && ((syn & (syn - 8'd1)) == 8'd0);
        assign sec[l] = (|mask) || onehot;
        assign ded[l] = syn_nz && !sec[l];
        assign rd_word[8*l +: 8] = row_dout_i[8*l +: 8] ^ mask;
      end
    end
    if (HARDEN && !ECC_BYTE) begin : g_dec_word
      wire [63:0] d64_unused;
      wire [7:0]  syn;
      wire        sec_dec_unused, ded_dec_unused;
      secded_dec u_dec (
          .code_in  ({1'b0, row_dout_i[38:32], 32'h0, row_dout_i[31:0]}),
          .data_out (d64_unused),
          .syndrome (syn),
          .sec      (sec_dec_unused),
          .ded      (ded_dec_unused)
      );
      wire [31:0] mask;
      genvar b;
      for (b = 0; b < 32; b = b + 1) begin : g_bit
        assign mask[b] = (syn == h_col[b]);
      end
      wire syn_nz  = |syn;
      wire onehot  = syn_nz && ((syn & (syn - 8'd1)) == 8'd0);
      assign sec[0]   = (|mask) || onehot;
      assign ded[0]   = syn_nz && !sec[0];
      assign sec[3:1] = 3'b000;
      assign ded[3:1] = 3'b000;
      assign rd_word  = row_dout_i[31:0] ^ mask;
    end
    if (!HARDEN) begin : g_dec_plain
      assign rd_word = row_dout_i[31:0];
      assign sec     = 4'b0000;
      assign ded     = 4'b0000;
    end
  endgenerate

  wire sec_any = |sec;
  wire ded_any = |ded;

  // ---- the response ------------------------------------------------
  //
  // rd0 marks a response whose row_dout_i is THIS request's row. A
  // write response carries no data (soc_bus.v rule 3), the row port
  // holds its last read across a write, and a report raised on that
  // stale row would be a report of somebody else's read.
  reg rv0, er0, rd0;
  reg [AW-1:0] row_q;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rv0   <= 1'b0;
      er0   <= 1'b0;
      rd0   <= 1'b0;
      row_q <= {AW{1'b0}};
    end else begin
      rv0 <= req_i;
      er0 <= write_attempt && RO;
      rd0 <= req_i && !we_i;
      if (req_i) row_q <= bus_row;
    end
  end

  wire rsp_rd = rv0 && rd0;
  // An uncorrectable word is a bus error. The fabric carries err in the
  // response cycle and Ibex takes an access fault: the word is never
  // consumed.
  wire err0 = er0 || (rsp_rd && ded_any);

  generate
  if (!RDREG) begin : g_rd1
    assign rvalid_o = rv0;
    assign rdata_o  = rd_word;
    assign err_o    = err0;
  end
  if (RDREG) begin : g_rd2
    reg        rv1, er1;
    reg [31:0] rd1;
    always @(posedge clk_i or negedge rst_ni) begin
      if (!rst_ni) begin
        rv1 <= 1'b0; rd1 <= 32'h0; er1 <= 1'b0;
      end else begin
        rv1 <= rv0;
        er1 <= err0;
        if (rv0) rd1 <= rd_word;
      end
    end
    assign rvalid_o = rv1;
    assign rdata_o  = rd1;
    assign err_o    = er1;
  end
  endgenerate

  // ---- the scrubber ------------------------------------------------
  wire idle = !req_i;
  wire s_go;        // issue a scrub read this cycle
  wire s_hit;       // last cycle's scrub read is on row_dout_i and the port is free
  wire s_wb;        // and something in it needs writing back
  wire [AW-1:0] sptr_w;

  generate
    if (HARDEN) begin : g_scrub
      reg [AW-1:0] sptr;
      reg [15:0]   stick;
      reg          srd_q;

      wire s_due = scrub_en_i && (stick == 16'd0);
      assign s_go   = s_due && idle && !srd_q;
      assign s_hit  = srd_q && idle;
      assign s_wb   = s_hit && sec_any;
      assign sptr_w = sptr;

      always @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
          sptr  <= {AW{1'b0}};
          stick <= 16'd0;
          srd_q <= 1'b0;
        end else begin
          srd_q <= s_go;
          if (s_go)               stick <= scrub_ivl_i;
          else if (stick != 16'd0) stick <= stick - 16'd1;
          // The row was examined -- clean, repaired or uncorrectable --
          // so move on. A read the bus pre-empted is not examined and
          // the pointer stays.
          if (s_hit) sptr <= sptr + {{(AW-1){1'b0}}, 1'b1};
        end
      end
    end
    if (!HARDEN) begin : g_noscrub
      assign s_go   = 1'b0;
      assign s_hit  = 1'b0;
      assign s_wb   = 1'b0;
      assign sptr_w = {AW{1'b0}};
    end
  endgenerate

  // ---- the write path ----------------------------------------------
  //
  // The encoders cover the bus word on a bus cycle and the CORRECTED
  // word on a scrub write-back; req_i is what tells them apart and the
  // two cannot coincide, because s_wb requires idle.
  wire [31:0] enc_in = req_i ? wdata_i : rd_word;

  wire [RW-1:0] bm_bus;   // the bus write's mask, from be_i
  wire [RW-1:0] bm_wb;    // the scrub write-back's mask, from sec

  generate
    if (HARDEN && ECC_BYTE) begin : g_enc_byte
      genvar l;
      for (l = 0; l < 4; l = l + 1) begin : g_lane
        wire [7:0]  chk;
        wire [71:0] code_unused;
        secded_enc u_enc (
            .data_in   ({56'h0, enc_in[8*l +: 8]}),
            .check_out (chk),
            .code_out  (code_unused)
        );
        assign row_din_o[8*l +: 8]    = enc_in[8*l +: 8];
        assign row_din_o[32+8*l +: 8] = chk;
        assign bm_bus[8*l +: 8]       = {8{be_i[l]}};
        assign bm_bus[32+8*l +: 8]    = {8{be_i[l]}};
        assign bm_wb[8*l +: 8]        = {8{sec[l]}};
        assign bm_wb[32+8*l +: 8]     = {8{sec[l]}};
      end
    end
    if (HARDEN && !ECC_BYTE) begin : g_enc_word
      wire [7:0]  chk;
      wire [71:0] code_unused;
      secded_enc u_enc (
          .data_in   ({32'h0, enc_in}),
          .check_out (chk),
          .code_out  (code_unused)
      );
      // chk[7] is identically zero over a 32-bit word (regfile_secded
      // C4) and is not stored.
      assign row_din_o = {chk[6:0], enc_in};
      // RO: the bus never writes, so its mask is never applied.
      assign bm_bus    = {RW{1'b0}};
      assign bm_wb     = {RW{1'b1}};
    end
    if (!HARDEN) begin : g_enc_plain
      assign row_din_o = {{CW{1'b0}}, enc_in};
      assign bm_bus    = {{CW{1'b0}}, {8{be_i[3]}}, {8{be_i[2]}},
                                      {8{be_i[1]}}, {8{be_i[0]}}};
      assign bm_wb     = {RW{1'b0}};
    end
  endgenerate

  // ---- the row port ------------------------------------------------
  assign row_en_o   = req_i || s_go || s_wb;
  assign row_we_o   = do_write || s_wb;
  assign row_addr_o = req_i ? bus_row : sptr_w;
  assign row_bm_o   = req_i ? bm_bus  : bm_wb;

  // ---- the reports -------------------------------------------------
  assign sec_o      = s_wb;
  assign rd_o       = rsp_rd && sec_any;
  assign ded_o      = (rsp_rd || s_hit) && ded_any;
  assign evt_addr_o = {{(32-AW-2){1'b0}}, (s_hit ? sptr_w : row_q), 2'b00};

`ifdef FORMAL
`include "soc_mem_ecc_int_props.v"
`endif

endmodule
