// =====================================================================
// COST PROBE -- NOT VERIFIED, NOT PART OF THE SOC
//
// This file exists for one purpose only: to be synthesised so that the
// silicon area of a real AHB-lite fabric can be measured and compared
// against keeping Ibex's native req/gnt/rvalid memory protocol.
//
//   * It is synthesised and area-measured only.
//   * It has NO testbench, NO simulation, NO formal proof. Nothing in
//     this file has been shown to be functionally correct.
//   * It is not instantiated anywhere in the SoC and must not be.
//   * It must not be used as if it were verified RTL. If any of it is
//     ever wanted for real it has to be re-reviewed and verified from
//     scratch first.
// =====================================================================
//
// ahbl2apb -- AHB-lite slave port to APB3 master port.
//
// APB3 is a two-phase protocol: SETUP with PSEL high and PENABLE low,
// then ACCESS with both high, held until PREADY. An AHB transfer
// therefore costs a minimum of two bus cycles here and the AHB slave
// port has to insert wait states with HREADYOUT for all of them. That is
// unavoidable and is a property of APB, not of this implementation.
//
// Address and control are captured from the AHB address phase because
// the APB transfer outlives it. PWDATA is taken straight from HWDATA
// with no register: AMBA requires an AHB master to hold HWDATA valid for
// the whole of an extended data phase, so the data is still there when
// APB needs it. PRDATA is likewise passed straight out on HRDATA in the
// cycle HREADYOUT goes high, which avoids a second 32-bit register.
//
// Decode: PSEL is eight 4 KiB slots inside a 1 MiB window, taken from
// PADDR[19:12]. Only slots 0..7 exist, so PADDR[19:15] must be zero;
// anything else in the window is unmapped and gets the AMBA-mandated
// two-cycle ERROR response without any APB transfer being started.
//
// PSLVERR from the peripheral is likewise turned into the two-cycle AHB
// ERROR, which the ibex2ahbl bridge upstream collapses back into one
// Ibex rvalid with err set.
//
module ahbl2apb (
  input  wire        clk_i,
  input  wire        rst_ni,

  // AHB-lite slave port
  input  wire        hsel_i,
  input  wire [31:0] haddr_i,
  input  wire [1:0]  htrans_i,
  input  wire        hwrite_i,
  input  wire [2:0]  hsize_i,
  input  wire [31:0] hwdata_i,
  input  wire        hready_i,
  output wire [31:0] hrdata_o,
  output wire        hreadyout_o,
  output wire        hresp_o,

  // APB3 master port
  output wire [7:0]  psel_o,
  output wire        penable_o,
  output wire [31:0] paddr_o,
  output wire        pwrite_o,
  output wire [31:0] pwdata_o,
  output wire [3:0]  pstrb_o,
  input  wire [31:0] prdata_i,
  input  wire        pready_i,
  input  wire        pslverr_i
);

  localparam [2:0] ST_IDLE   = 3'd0;
  localparam [2:0] ST_SETUP  = 3'd1;
  localparam [2:0] ST_ACCESS = 3'd2;
  localparam [2:0] ST_ERR1   = 3'd3;
  localparam [2:0] ST_ERR2   = 3'd4;

  reg [2:0]  st_q;
  reg [31:0] paddr_q;
  reg        pwrite_q;
  reg [3:0]  pstrb_q;

  // ---- address phase acceptance ---------------------------------------
  wire ap_accept = hsel_i & htrans_i[1] & hready_i;

  // Slots 0..7 of the 1 MiB window are populated; the rest is a hole.
  wire dec_ok = (haddr_i[19:15] == 5'b0);

  // ---- byte strobes from HSIZE and the low address bits ----------------
  reg [3:0] strb_d;
  always @(*) begin
    case (hsize_i[1:0])
      2'd0: strb_d = 4'b0001 << haddr_i[1:0];        // byte
      2'd1: strb_d = haddr_i[1] ? 4'b1100 : 4'b0011; // halfword
      default: strb_d = 4'b1111;                     // word
    endcase
  end

  // ---- APB outputs ------------------------------------------------------
  wire apb_active = (st_q == ST_SETUP) | (st_q == ST_ACCESS);

  reg [7:0] psel_d;
  always @(*) begin
    if (apb_active) begin
      psel_d = 8'b1 << paddr_q[14:12];
    end else begin
      psel_d = 8'b0;
    end
  end

  assign psel_o    = psel_d;
  assign penable_o = (st_q == ST_ACCESS);
  assign paddr_o   = paddr_q;
  assign pwrite_o  = pwrite_q;
  assign pwdata_o  = hwdata_i;
  assign pstrb_o   = pwrite_q ? pstrb_q : 4'b0000;

  // ---- AHB response -----------------------------------------------------
  // A successful APB access completes in the same cycle PREADY is seen,
  // so HRDATA is PRDATA combinationally. PSLVERR forces the two-cycle
  // error path instead.
  wire acc_ok  = (st_q == ST_ACCESS) & pready_i & ~pslverr_i;
  wire acc_err = (st_q == ST_ACCESS) & pready_i &  pslverr_i;

  assign hrdata_o    = prdata_i;
  assign hreadyout_o = (st_q == ST_IDLE) | (st_q == ST_ERR2) | acc_ok;
  assign hresp_o     = (st_q == ST_ERR1) | (st_q == ST_ERR2) | acc_err;

  // Cycles in which a new AHB address phase can be taken. These are
  // exactly the cycles where hreadyout_o is high.
  wire can_take = (st_q == ST_IDLE) | (st_q == ST_ERR2) | acc_ok;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      st_q     <= ST_IDLE;
      paddr_q  <= 32'b0;
      pwrite_q <= 1'b0;
      pstrb_q  <= 4'b0;
    end else begin
      case (st_q)
        ST_SETUP: begin
          st_q <= ST_ACCESS;
        end
        ST_ERR1: begin
          st_q <= ST_ERR2;
        end
        default: begin
          // ST_IDLE, ST_ERR2, and ST_ACCESS once PREADY has been seen.
          if (can_take) begin
            if (ap_accept) begin
              paddr_q  <= haddr_i;
              pwrite_q <= hwrite_i;
              pstrb_q  <= strb_d;
              st_q     <= dec_ok ? ST_SETUP : ST_ERR1;
            end else begin
              st_q <= ST_IDLE;
            end
          end
          // ST_ACCESS without PREADY simply stays put.
        end
      endcase
    end
  end

endmodule
