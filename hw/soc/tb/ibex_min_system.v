// A minimal system around the sv2v-converted Ibex, in Verilog-2005.
//
// WHY NOT ibex_simple_system. Upstream ships examples/simple_system,
// which is the natural thing to reach for, but it is SystemVerilog that
// pulls in the OpenTitan bus fabric (`bus.sv`), `simulator_ctrl`, a
// `prim_ram_2p` and a DPI-C `simutil_memload` for image loading. It is
// written for Verilator. Getting it through sv2v would put a bus, a
// memory model and a DPI shim into the gate for the CPU -- and if any of
// those failed to convert, the result would say nothing about whether
// the CPU converted. This file exists so that what is being simulated is
// the core and nothing else.
//
// Memory model: one word-addressed array serving both ports.
//   - Address phase completes in the cycle req is asserted (gnt = req).
//   - Data phase one cycle later (rvalid registered).
//   That is the simplest protocol-legal behaviour; Ibex's LSU and
//   prefetch buffer both tolerate it (doc/02_user/integration.rst).
//
// Test control region, decoded on the data port only:
//   0x0010_0000   write: character out (low byte) -- putchar
//   0x0010_0004   write: halt simulation, value is the exit code
//                        (0 = pass)
//
// The control region sits outside the RAM aperture on purpose, so no
// address the linker can hand to code or data is shadowed by it. The
// program image is a $readmemh file of 32-bit words.

`timescale 1ns / 1ps

module ibex_min_system #(
    parameter integer MEM_WORDS = 4096,   // 16 KiB
    parameter [31:0]  BOOT_ADDR = 32'h0000_0000
) (
    input  wire        clk_i,
    input  wire        rst_ni,
    output wire        halted_o,
    output wire [31:0] exit_code_o,
    output wire        alert_minor_o,
    output wire        alert_major_internal_o,
    output wire        alert_major_bus_o,
    output wire        double_fault_seen_o,
    output wire        core_sleep_o
);

  localparam [31:0] ADDR_PUTC = 32'h0010_0000;
  localparam [31:0] ADDR_HALT = 32'h0010_0004;

  reg [31:0] mem [0:MEM_WORDS-1];

  // ---------------- instruction port ----------------
  wire        instr_req;
  wire [31:0] instr_addr;
  reg         instr_rvalid;
  reg  [31:0] instr_rdata;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      instr_rvalid <= 1'b0;
      instr_rdata  <= 32'h0;
    end else begin
      instr_rvalid <= instr_req;
      if (instr_req) instr_rdata <= mem[instr_addr[31:2] % MEM_WORDS];
    end
  end

  // ---------------- data port ----------------
  wire        data_req;
  wire        data_we;
  wire [3:0]  data_be;
  wire [31:0] data_addr;
  wire [31:0] data_wdata;
  reg         data_rvalid;
  reg  [31:0] data_rdata;

  wire is_putc = data_req && data_we && (data_addr == ADDR_PUTC);
  wire is_halt = data_req && data_we && (data_addr == ADDR_HALT);
  wire is_ram  = data_req && !is_putc && !is_halt;

  reg        halted;
  reg [31:0] exit_code;

  integer widx;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      data_rvalid <= 1'b0;
      data_rdata  <= 32'h0;
      halted      <= 1'b0;
      exit_code   <= 32'hFFFF_FFFF;
    end else begin
      data_rvalid <= data_req;
      if (is_ram) begin
        widx = data_addr[31:2] % MEM_WORDS;
        if (data_we) begin
          if (data_be[0]) mem[widx][7:0]   <= data_wdata[7:0];
          if (data_be[1]) mem[widx][15:8]  <= data_wdata[15:8];
          if (data_be[2]) mem[widx][23:16] <= data_wdata[23:16];
          if (data_be[3]) mem[widx][31:24] <= data_wdata[31:24];
        end else begin
          data_rdata <= mem[widx];
        end
      end
      if (is_putc) $write("%c", data_wdata[7:0]);
      if (is_halt) begin
        halted    <= 1'b1;
        exit_code <= data_wdata;
      end
    end
  end

  assign halted_o    = halted;
  assign exit_code_o = exit_code;

  // ---------------- the core ----------------
  // Only the parameters this project sets are overridden; every other
  // parameter keeps ibex_top's own default. The values are the integer
  // encodings from ext/ibex/rtl/ibex_pkg.sv, the same ones
  // flow/syn_ibex.sh gives Yosys, so the simulated configuration and the
  // synthesised configuration are the same configuration.
  //   BaseIsa 0 = BaseIsaRV32I,  RV32M 2 = RV32MFast,
  //   RV32B   0 = RV32BNone,     RV32ZC 0 = RV32Zca,
  //   RegFile 0 = RegFileFF
  ibex_top #(
      .BaseIsa         (0),
      .PMPEnable       (`IBEX_PMPENABLE),
      .PMPGranularity  (0),
      .PMPNumRegions   (4),
      .MHPMCounterNum  (0),
      .MHPMCounterWidth(40),
      .RV32E           (0),
      .RV32M           (2),
      .RV32B           (0),
      .RV32ZC          (0),
      .RegFile         (0),
      .BranchTargetALU (0),
      .WritebackStage  (0),
      .ICache          (0),
      .ICacheECC       (0),
      .BranchPredictor (0),
      .DbgTriggerEn    (0),
      .SecureIbex      (`IBEX_SECUREIBEX),
      .ICacheScramble  (0)
  ) u_ibex (
      .clk_i  (clk_i),
      .rst_ni (rst_ni),
      .test_en_i(1'b0),

      .ram_cfg_icache_tag_i  (24'h0),
      .ram_cfg_icache_tag_o  (),
      .ram_cfg_icache_data_i (24'h0),
      .ram_cfg_icache_data_o (),

      // ibex_pkg::IbexMuBiOff = 4'b1010. BaseIsa is RV32I, so the
      // CHERIoT half of the dual-ISA core is held off.
      .cheriot_enable_i (4'b1010),

      .hart_id_i             (32'h0),
      .boot_addr_i           (BOOT_ADDR),
      .trvk_heap_base_addr_i (32'h0),

      .instr_req_o        (instr_req),
      .instr_gnt_i        (instr_req),
      .instr_rvalid_i     (instr_rvalid),
      .instr_addr_o       (instr_addr),
      .instr_rdata_i      (instr_rdata),
      .instr_rdata_intg_i (7'h0),
      .instr_err_i        (1'b0),

      .data_req_o        (data_req),
      .data_gnt_i        (data_req),
      .data_rvalid_i     (data_rvalid),
      .data_we_o         (data_we),
      .data_be_o         (data_be),
      .data_addr_o       (data_addr),
      .data_wdata_o      (data_wdata),
      .data_wdata_intg_o (),
      .data_tag_o        (),
      .data_rdata_i      (data_rdata),
      .data_rdata_intg_i (7'h0),
      .data_tag_i        (1'b0),
      .data_err_i        (1'b0),

      .trvk_revbm_req_o        (),
      .trvk_revbm_gnt_i        (1'b0),
      .trvk_revbm_rvalid_i     (1'b0),
      .trvk_revbm_addr_o       (),
      .trvk_revbm_rdata_i      (32'h0),
      .trvk_revbm_rdata_intg_i (7'h0),
      .trvk_revbm_err_i        (1'b0),

      .irq_software_i (1'b0),
      .irq_timer_i    (1'b0),
      .irq_external_i (1'b0),
      .irq_fast_i     (15'h0),
      .irq_nm_i       (1'b0),

      .scramble_key_valid_i (1'b0),
      .scramble_key_i       (128'h0),
      .scramble_nonce_i     (64'h0),
      .scramble_req_o       (),

      .debug_req_i         (1'b0),
      .crash_dump_o        (),
      .double_fault_seen_o (double_fault_seen_o),

      // ibex_pkg::IbexMuBiOn = 4'b0101.
      .fetch_enable_i        (4'b0101),
      .mcounteren_writable_i (4'b1010),

      .alert_minor_o          (alert_minor_o),
      .alert_major_internal_o (alert_major_internal_o),
      .alert_major_bus_o      (alert_major_bus_o),
      .core_sleep_o           (core_sleep_o),

      .scan_rst_ni (1'b1),

      .lockstep_cmp_en_o        (),
      .data_req_shadow_o        (),
      .data_we_shadow_o         (),
      .data_be_shadow_o         (),
      .data_addr_shadow_o       (),
      .data_wdata_shadow_o      (),
      .data_wdata_intg_shadow_o (),
      .instr_req_shadow_o       (),
      .instr_addr_shadow_o      ()
  );

endmodule
