// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Behavioural model of a Winbond W25Q128JV serial flash, written from
// its datasheet and not from the controller that talks to it.
//
// =====================================================================
// WHAT THIS IS
// =====================================================================
//
// The specification hw/soc/rtl/soc_qspi.v is tested against. Every
// behaviour and every number below is taken from "W25Q128JV, 3V 128M-bit
// serial flash memory with dual/quad SPI", Winbond, Revision M,
// publication release date 2024-12-24, cited by section and table so a
// reader can check each one; nothing was taken from soc_qspi.v. A model
// derived from the RTL would prove that the RTL agrees with itself,
// which is this repository's recurring vacuity defect (docs/09 B.1).
//
// The part: 16 MiB, 3-byte addresses, SPI mode 0 or 3 (this model
// requires mode 0: CLK low while /CS is not asserted, section 6.1),
// standard/dual/quad lanes, QE bit gating the quad instructions, /WP and
// /HOLD on IO2 and IO3 while QE is 0.
//
// WHAT IT CHECKS, and counts in `violations`:
//
//   AC timing, table 9.6, against $realtime in nanoseconds:
//     tSLCH   /CS active setup to first CLK rising edge      >= 3 ns
//     tCHSL   last CLK rising edge to /CS falling             >= 3 ns
//     tCHSH   last CLK rising edge to /CS rising              >= 3 ns
//     tSHSL1  /CS deselect time after a read                  >= 10 ns
//     tSHSL2  /CS deselect time after a write, program, erase >= 50 ns
//     tDVCH   input setup before a CLK rising edge            >= 1 ns
//     tCHDX   input hold after a CLK rising edge              >= 2 ns
//     FR      CLK period for everything but Read Data (03h)   >= 1/133 MHz
//     fR      CLK period for Read Data (03h)                  >= 1/50 MHz
//     tCLH, tCLL  CLK high and low time >= 45 % of 1/133 MHz  (note 1)
//   Protocol:
//     mode 0: /CS may fall or rise only while CLK is low (section 6.1)
//     a quad instruction (6Bh, EBh) with QE = 0 is refused (8.2.9,
//       8.2.11: "The Quad Enable (QE) bit ... must be set")
//     /HOLD (IO3) low at a CLK rising edge while QE = 0 (section 4.4:
//       the device would pause; here it is counted, because a
//       controller that lets it happen has a wiring or drive defect)
//     a Write Status Register without a preceding 06h or 50h (8.2.5)
//     an instruction other than Read Status while BUSY (8.2.5: "the
//       Read Status Register instruction may still be accessed")
//     an EBh frame whose M5-4 are 1,0 enters continuous read mode
//       (8.2.11); this controller never leaves it, so it is counted
//     a program frame that ends mid-byte
//     an opcode this model does not implement
//
// WHAT IT PRODUCES on the pins, with the datasheet's output timing:
// outputs change on the falling edge of CLK, old value held for tCLQX
// (1.5 ns min), then X, then the new value valid at tCLQV (6 ns max)
// after the edge -- the worst case of the table, so a controller that
// samples too early reads X and fails. After /CS rises the outputs stay
// driven for tSHQZ (7 ns max) and then release.
//
// WHAT IT DOES NOT MODEL, stated so the model is not mistaken for the
// part: dual-lane instructions, QPI mode, 4-byte addressing, wrap
// reads (77h), the security registers, block and chip erase, suspend
// and resume, power-down, the /RESET pin, the write-protect pins as
// protection (SRP and the block-protect bits are not implemented; SR1
// reads BUSY and WEL only), the unique ID, SFDP, Status Register-3,
// program-time data retention effects, and any electrical property
// (drive strength, capacitance, voltage). The busy times tW, tPP, tSE
// and tRST default to the table's maxima and the testbenches SCALE THEM
// DOWN by parameter, and say so: a 15 ms wait is 1.5 million cycles of
// simulation and proves nothing a 2 us wait does not. The storage
// behind the array is MEM_BYTES, smaller than the part's 16 MiB;
// addresses beyond it read as erased (FFh) and are counted in
// `above_model`.
//
// A BEHAVIOURAL MODEL IS NOT A FLASH. It has no process, no temperature
// and no voltage; it does not age, it does not need erasing before it
// is programmed in this model's initial state, and its timing is a set
// of inequalities checked in simulation time. What passing against it
// establishes is that the controller obeys the datasheet's published
// contract as this file states it -- not that the controller works with
// a device.

`timescale 1ns / 1ps

module flash_w25q128jv #(
    // Modelled storage. The part is 1 << 24 bytes (2. FEATURES:
    // "128M-bit / 16M-byte"); addresses above MEM_BYTES read FFh.
    parameter integer MEM_BYTES  = 1 << 17,
    // Factory default of the non-volatile QE bit: 0 for ordering
    // options IM and JM (7.1.4).
    parameter         QE_DEFAULT = 1'b0,
    // Busy times, table 9.6 maxima, in ns. Testbenches scale them.
    parameter real    T_W_NS   = 15000000.0,   // tW   15 ms
    parameter real    T_PP_NS  = 3000000.0,    // tPP  3 ms
    parameter real    T_SE_NS  = 400000000.0,  // tSE  400 ms
    parameter real    T_RST_NS = 30000.0       // tRST 30 us
) (
    input  wire       cs_n,
    input  wire       sck,
    inout  wire [3:0] io
);

  // ---- table 9.6, in ns ----------------------------------------------
  localparam real T_SLCH  = 3.0;
  localparam real T_CHSL  = 3.0;
  localparam real T_CHSH  = 3.0;
  localparam real T_SHSL1 = 10.0;
  localparam real T_SHSL2 = 50.0;
  localparam real T_DVCH  = 1.0;
  localparam real T_CHDX  = 2.0;
  localparam real P_FR    = 1000.0 / 133.0;   // 7.519 ns
  localparam real P_FR03  = 1000.0 / 50.0;    // 20 ns
  localparam real T_CLHL  = 0.45 * P_FR;      // note 1: 45 % of Pc
  localparam real T_CLQV  = 6.0;
  localparam real T_CLQX  = 1.5;
  localparam real T_SHQZ  = 7.0;

  // ---- table 8.1.1, Manufacturer and Device Identification -----------
  localparam [7:0] ID_MF   = 8'hEF;   // Winbond
  localparam [7:0] ID_TYPE = 8'h40;   // ID15-ID8 of 4018h
  localparam [7:0] ID_CAP  = 8'h18;   // ID7-ID0

  // ---- the array ---------------------------------------------------------
  reg [7:0] mem [0:MEM_BYTES-1];
  integer init_i;
  initial for (init_i = 0; init_i < MEM_BYTES; init_i = init_i + 1)
    mem[init_i] = 8'hFF;

  // ---- status ----------------------------------------------------------
  reg  qe_nv;          // Status Register-2 S9, non-volatile copy
  reg  qe;             // the working (volatile) copy, 8.2.5
  reg  wel;            // Status Register-1 S1, 7.1.2
  reg  vwel;           // 50h has been issued, 8.2.2
  reg  reset_armed;    // 66h has been issued, 8.2.43
  real busy_until;     // BUSY (S0) is 1 until this time
  // A function and not a wire: a continuous assignment is not
  // re-evaluated when only $realtime has moved.
  function is_busy;
    input dummy;
    begin
      is_busy = ($realtime < busy_until);
    end
  endfunction

  // ---- counters the testbench reads ----------------------------------------
  integer violations   = 0;
  integer above_model  = 0;
  integer frames       = 0;
  integer quad_unaligned = 0;   // table 9.6 note 6, advisory
  integer last_opcode  = -1;

  // ---- timing bookkeeping ----------------------------------------------
  real t_cs_fall, t_cs_rise, t_rise, t_fall, t_io_chg;
  real min_period;
  real deselect_needed;       // tSHSL1 or tSHSL2 for the next frame
  integer nrise;              // rising edges seen in this frame

  task violation;
    input [8*80-1:0] what;
    begin
      violations = violations + 1;
      $display("[FLASH %m] VIOLATION at %0t: %0s", $realtime, what);
    end
  endtask

  // ---- the frame -------------------------------------------------------------
  reg [7:0]  opcode;
  reg [23:0] addr;
  reg [7:0]  mode;
  reg [7:0]  din;
  integer    din_bits;
  integer    din_count;       // complete data bytes received
  reg [7:0]  sr2_new;
  reg [7:0]  page_buf [0:255];
  integer    pg_i;

  // What the opcode says the frame is.
  reg        has_addr, addr_quad, has_mode, data_out, data_quad, data_in;
  integer    n_dummy;
  reg        refused;         // decoded, but the part will not act on it

  // Output side.
  reg        out_on;          // data-out phase reached
  reg        drv;             // outputs driven
  reg        drv_x;           // in the tCLQX..tCLQV window
  reg [3:0]  drv_val;
  reg [7:0]  out_byte;
  integer    out_unit;        // units of the current byte sent
  reg [23:0] out_addr;
  integer    id_idx;

  assign io[0] = (drv && data_quad) ? (drv_x ? 1'bx : drv_val[0]) : 1'bz;
  assign io[1] = (drv)              ? (drv_x ? 1'bx : drv_val[1]) : 1'bz;
  assign io[2] = (drv && data_quad) ? (drv_x ? 1'bx : drv_val[2]) : 1'bz;
  assign io[3] = (drv && data_quad) ? (drv_x ? 1'bx : drv_val[3]) : 1'bz;

  function [7:0] read_byte;
    input [23:0] a;
    begin
      if (a < MEM_BYTES) read_byte = mem[a];
      else begin
        read_byte = 8'hFF;
        above_model = above_model + 1;
      end
    end
  endfunction

  function [7:0] sr1;
    input dummy;
    begin
      sr1 = {6'b0, wel, is_busy(1'b0)};
    end
  endfunction

  function [7:0] sr2;
    input dummy;
    begin
      sr2 = {6'b0, qe, 1'b0};
    end
  endfunction

  // The byte the output phase presents next.
  function [7:0] next_out_byte;
    input dummy;
    begin
      case (opcode)
        8'h9F: begin
          next_out_byte = (id_idx % 3 == 0) ? ID_MF
                        : (id_idx % 3 == 1) ? ID_TYPE : ID_CAP;
        end
        8'h05: next_out_byte = sr1(1'b0);
        8'h35: next_out_byte = sr2(1'b0);
        default: next_out_byte = read_byte(out_addr);
      endcase
    end
  endfunction

  task advance_out_byte;
    begin
      id_idx   = id_idx + 1;
      out_addr = out_addr + 24'd1;     // rolls over at 16 MiB, 8.2.6
    end
  endtask

  initial begin
    qe_nv = QE_DEFAULT; qe = QE_DEFAULT; wel = 1'b0; vwel = 1'b0;
    reset_armed = 1'b0; busy_until = -1.0;
    t_cs_fall = -1.0e9; t_cs_rise = -1.0e9; t_rise = -1.0e9; t_fall = -1.0e9;
    t_io_chg = -1.0e9; min_period = 1.0e9; deselect_needed = 0.0; nrise = 0;
    drv = 1'b0; drv_x = 1'b0; drv_val = 4'h0; out_on = 1'b0;
  end

  // ---- input-side timing -------------------------------------------------------
  always @(io) begin
    // Hold: an input that changes within tCHDX of a rising edge, while
    // the part is sampling inputs.
    if (!cs_n && !out_on && ($realtime - t_rise) < T_CHDX
        && ($realtime - t_rise) >= 0.0 && nrise > 0)
      violation("tCHDX: input changed within 2 ns after a CLK rising edge");
    t_io_chg = $realtime;
  end

  // ---- /CS falling: a frame begins -----------------------------------------------
  always @(negedge cs_n) begin
    frames = frames + 1;
    if (sck !== 1'b0)
      violation("mode 0: /CS fell while CLK was not low (6.1)");
    if (($realtime - t_rise) < T_CHSL)
      violation("tCHSL: /CS fell within 3 ns of a CLK rising edge");
    if (t_cs_rise > 0.0 && ($realtime - t_cs_rise) < deselect_needed)
      violation("tSHSL: /CS deselect time too short (10 ns read, 50 ns write)");
    t_cs_fall  = $realtime;
    nrise      = 0;
    min_period = 1.0e9;
    opcode = 8'h00; addr = 24'h0; mode = 8'h00; din = 8'h00;
    din_bits = 0; din_count = 0;
    has_addr = 0; addr_quad = 0; has_mode = 0; data_out = 0; data_quad = 0;
    data_in = 0; n_dummy = 0; refused = 0;
    out_on = 0; out_unit = 0; id_idx = 0;
    for (pg_i = 0; pg_i < 256; pg_i = pg_i + 1) page_buf[pg_i] = 8'hFF;
  end

  // ---- CLK rising: the part samples ---------------------------------------------
  integer k;         // clock index after the opcode
  integer addr_clk, mode_clk;
  always @(posedge sck) if (!cs_n) begin
    // timing
    if (nrise == 0) begin
      if (($realtime - t_cs_fall) < T_SLCH)
        violation("tSLCH: first CLK rising edge within 3 ns of /CS falling");
    end else begin
      if (($realtime - t_rise) < min_period) min_period = $realtime - t_rise;
      if (($realtime - t_fall) < T_CLHL)
        violation("tCLL: CLK low time under 45 % of the 133 MHz period");
    end
    if (($realtime - t_io_chg) < T_DVCH && !out_on)
      violation("tDVCH: input changed within 1 ns before a CLK rising edge");
    if (!qe && io[3] === 1'b0)
      violation("/HOLD (IO3) low at a CLK rising edge with QE = 0 (4.4)");
    t_rise = $realtime;

    // the opcode, MSB first on IO0 (8.1: "instruction code ... MSB first")
    if (nrise < 8) begin
      opcode = {opcode[6:0], io[0]};
      if (nrise == 7) decode_opcode;
    end else if (!refused) begin
      k = nrise - 8;
      addr_clk = has_addr ? (addr_quad ? 6 : 24) : 0;
      mode_clk = has_mode ? 2 : 0;
      if (k < addr_clk) begin
        addr = addr_quad ? {addr[19:0], io} : {addr[22:0], io[0]};
      end else if (k < addr_clk + mode_clk) begin
        mode = {mode[3:0], io};
        if (k == addr_clk + mode_clk - 1) begin
          // 8.2.11: M5-4 = (1,0) enters continuous read mode
          if (mode[5:4] == 2'b10)
            violation("EBh with M5-4 = 1,0 enters continuous read mode");
        end
      end else if (k < addr_clk + mode_clk + n_dummy) begin
        // dummy: nothing sampled
      end else if (data_in) begin
        din = {din[6:0], io[0]};
        din_bits = din_bits + 1;
        if (din_bits == 8) begin
          din_bits = 0;
          if (opcode == 8'h31 && din_count == 0) sr2_new = din;
          if (opcode == 8'h02) begin
            // 8.2.13: the address wraps within the 256-byte page
            page_buf[addr[7:0]] = din;
            addr = {addr[23:8], addr[7:0] + 8'd1};
          end
          din_count = din_count + 1;
        end
      end
      if (data_out && k == addr_clk + mode_clk + n_dummy - 1) begin
        // the last clock before data: the falling edge after this
        // rising edge carries the first data unit
        out_on   = 1;
        out_addr = addr;
        out_byte = next_out_byte(1'b0);
        out_unit = 0;
        // 8.2.6: the first byte is presented after the address; for the
        // ID and status reads there is no address
      end
    end
    if (data_out && !has_addr && n_dummy == 0 && nrise == 7 && !refused) begin
      out_on   = 1;
      out_addr = 24'h0;
      out_byte = next_out_byte(1'b0);
      out_unit = 0;
    end
    nrise = nrise + 1;
  end

  // ---- CLK falling: the part drives ----------------------------------------------
  always @(negedge sck) if (!cs_n) begin
    if (nrise > 0 && ($realtime - t_rise) < T_CLHL)
      violation("tCLH: CLK high time under 45 % of the 133 MHz period");
    t_fall = $realtime;
    if (out_on) begin
      drv <= 1'b1;
      // tCLQX: the old value holds for at least 1.5 ns; tCLQV: the new
      // one is valid within 6 ns. In between the pin is X.
      drv_x   <= #(T_CLQX) 1'b1;
      drv_x   <= #(T_CLQV) 1'b0;
      if (data_quad) begin
        drv_val <= #(T_CLQV) (out_unit == 0) ? out_byte[7:4] : out_byte[3:0];
        out_unit = out_unit + 1;
        if (out_unit == 2) begin
          advance_out_byte;
          out_byte = next_out_byte(1'b0);
          out_unit = 0;
        end
      end else begin
        drv_val <= #(T_CLQV) {2'b00, out_byte[7 - out_unit], 1'b0};
        out_unit = out_unit + 1;
        if (out_unit == 8) begin
          advance_out_byte;
          out_byte = next_out_byte(1'b0);
          out_unit = 0;
        end
      end
    end
  end

  // ---- /CS rising: the frame ends and the part acts -------------------------------
  always @(posedge cs_n) begin
    if (sck !== 1'b0)
      violation("mode 0: /CS rose while CLK was not low (6.1)");
    if (nrise > 0 && ($realtime - t_rise) < T_CHSH)
      violation("tCHSH: /CS rose within 3 ns of a CLK rising edge");
    if (nrise > 1) begin
      if (opcode == 8'h03) begin
        if (min_period < P_FR03)
          violation("fR: Read Data (03h) clocked faster than 50 MHz");
      end else if (min_period < P_FR)
        violation("FR: clocked faster than 133 MHz");
    end
    t_cs_rise = $realtime;
    // outputs release tSHQZ after /CS rises
    drv   <= #(T_SHQZ) 1'b0;
    drv_x <= #(T_SHQZ) 1'b0;
    out_on = 0;
    if (nrise >= 8 && !refused) complete_frame;
    else if (nrise > 0 && nrise < 8)
      violation("frame ended before a whole opcode was clocked in");
  end

  // ---- the opcode table, section 8.1.2 ----------------------------------------------
  task decode_opcode;
    begin
      last_opcode = opcode;
      deselect_needed = T_SHSL1;
      // 8.2.5: while BUSY only Read Status is accepted
      if (is_busy(1'b0) && opcode != 8'h05 && opcode != 8'h35) begin
        violation("instruction other than Read Status while BUSY (8.2.5)");
        refused = 1;
      end
      // 8.2.43: 99h acts only directly after 66h
      if (opcode != 8'h99 && opcode != 8'h66) reset_armed = 0;
      case (opcode)
        8'h06, 8'h04, 8'h50, 8'h66, 8'h99: begin  // no address, no data
          deselect_needed = T_SHSL2;
        end
        8'h9F, 8'h05, 8'h35: begin                // data out at once
          data_out = 1;
        end
        8'h31: begin                              // one data byte in
          data_in = 1; deselect_needed = T_SHSL2;
        end
        8'h03: begin has_addr = 1; data_out = 1; end
        8'h0B: begin has_addr = 1; n_dummy = 8; data_out = 1; end
        8'h6B: begin
          has_addr = 1; n_dummy = 8; data_out = 1; data_quad = 1;
          if (!qe) begin
            violation("Fast Read Quad Output (6Bh) with QE = 0 (8.2.9)");
            refused = 1;
          end
        end
        8'hEB: begin
          has_addr = 1; addr_quad = 1; has_mode = 1; n_dummy = 4;
          data_out = 1; data_quad = 1;
          if (!qe) begin
            violation("Fast Read Quad I/O (EBh) with QE = 0 (8.2.11)");
            refused = 1;
          end
        end
        8'h02: begin has_addr = 1; data_in = 1; deselect_needed = T_SHSL2; end
        8'h20: begin has_addr = 1; deselect_needed = T_SHSL2; end
        default: begin
          violation("opcode not implemented by this model");
          refused = 1;
        end
      endcase
    end
  endtask

  // ---- what the part does when /CS rises -----------------------------------------
  integer se_i;
  task complete_frame;
    begin
      if ((opcode == 8'h6B || opcode == 8'hEB) && addr[1:0] != 2'b00)
        quad_unaligned = quad_unaligned + 1;   // table 9.6 note 6
      case (opcode)
        8'h06: wel = 1'b1;                                  // 8.2.1
        8'h04: wel = 1'b0;                                  // 8.2.3
        8'h50: vwel = 1'b1;                                 // 8.2.2
        8'h66: reset_armed = 1'b1;                          // 8.2.43
        8'h99: if (reset_armed) begin                       // 8.2.43
          reset_armed = 1'b0; wel = 1'b0; vwel = 1'b0; qe = qe_nv;
          busy_until = $realtime + T_RST_NS;
        end
        8'h31: begin                                        // 8.2.5
          if (din_count < 1)
            violation("Write Status Register-2 with no data byte");
          else if (wel) begin
            qe_nv = sr2_new[1]; qe = sr2_new[1];
            busy_until = $realtime + T_W_NS;
            wel = 1'b0;
          end else if (vwel) begin
            qe = sr2_new[1];
            vwel = 1'b0;
          end else
            violation("Write Status Register without 06h or 50h first (8.2.5)");
        end
        8'h02: begin                                        // 8.2.13
          if (din_bits != 0)
            violation("Page Program frame ended mid-byte");
          if (!wel)
            violation("Page Program without Write Enable (8.2.13)");
          else if (din_count == 0)
            violation("Page Program with no data");
          else begin
            for (pg_i = 0; pg_i < 256; pg_i = pg_i + 1)
              if ({addr[23:8], pg_i[7:0]} < MEM_BYTES)
                mem[{addr[23:8], pg_i[7:0]}] =
                    mem[{addr[23:8], pg_i[7:0]}] & page_buf[pg_i];
            busy_until = $realtime + T_PP_NS;
            wel = 1'b0;
          end
        end
        8'h20: begin                                        // 8.2.15
          if (!wel)
            violation("Sector Erase without Write Enable (8.2.15)");
          else begin
            for (se_i = 0; se_i < 4096; se_i = se_i + 1)
              if ({addr[23:12], se_i[11:0]} < MEM_BYTES)
                mem[{addr[23:12], se_i[11:0]}] = 8'hFF;
            busy_until = $realtime + T_SE_NS;
            wel = 1'b0;
          end
        end
        default: ;                                          // reads act as they go
      endcase
    end
  endtask

endmodule
