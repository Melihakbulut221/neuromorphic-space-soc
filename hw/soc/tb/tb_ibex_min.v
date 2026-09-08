// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Icarus testbench for the sv2v-converted Ibex.
//
// Clock, reset, program load, timeout, and a pass/fail decision that
// requires ALL of:
//   - the program reached the halt write (it did not hang, and it did
//     not wander off and stop fetching)
//   - the exit code it wrote is zero (every self-check inside it passed)
//   - no alert fired while it ran (alert_major_* latch a detected fault;
//     under SecureIbex a lockstep mismatch raises alert_major_internal_o)
//   - double_fault_seen_o never asserted
//
// A run that hits the timeout fails. A run that halts with a non-zero
// code fails and prints the mask.

`timescale 1ns / 1ps

`ifndef IBEX_PMPENABLE
  `define IBEX_PMPENABLE 1
`endif
`ifndef IBEX_SECUREIBEX
  `define IBEX_SECUREIBEX 0
`endif
`ifndef PROG_HEX
  `define PROG_HEX "test_ibex.hex"
`endif
`ifndef TIMEOUT_CYCLES
  `define TIMEOUT_CYCLES 5000000
`endif

module tb_ibex_min;

  localparam integer MEM_WORDS = 4096;

  // Addresses of the handler's bookkeeping words, so a failing run can
  // report them. Overridden from the command line by flow/sim_ibex.sh,
  // which reads them out of the ELF symbol table -- hardcoding them
  // here would silently go stale the next time the program is edited.
`ifndef TRAP_MCAUSE_ADDR
  `define TRAP_MCAUSE_ADDR 32'h0
`endif
`ifndef TRAP_MEPC_ADDR
  `define TRAP_MEPC_ADDR 32'h0
`endif
`ifndef TRAP_COUNT_ADDR
  `define TRAP_COUNT_ADDR 32'h0
`endif
  localparam [31:0] TRAP_MCAUSE_ADDR = `TRAP_MCAUSE_ADDR;
  localparam [31:0] TRAP_MEPC_ADDR   = `TRAP_MEPC_ADDR;
  localparam [31:0] TRAP_COUNT_ADDR  = `TRAP_COUNT_ADDR;

  reg clk = 1'b0;
  reg rst_n = 1'b0;

  wire        halted;
  wire [31:0] exit_code;
  wire        alert_minor, alert_major_internal, alert_major_bus;
  wire        double_fault_seen, core_sleep;

  always #5 clk = ~clk;          // 100 MHz; functional only

  ibex_min_system #(
      .MEM_WORDS (MEM_WORDS),
      .BOOT_ADDR (32'h0000_0000)
  ) dut (
      .clk_i (clk),
      .rst_ni (rst_n),
      .halted_o (halted),
      .exit_code_o (exit_code),
      .alert_minor_o (alert_minor),
      .alert_major_internal_o (alert_major_internal),
      .alert_major_bus_o (alert_major_bus),
      .double_fault_seen_o (double_fault_seen),
      .core_sleep_o (core_sleep)
  );

  // Latch alerts: they are pulses, and a run must fail if one ever
  // fired, not only if one is firing when the program halts.
  // The two major alerts are latched SEPARATELY. They mean different
  // things and the difference is the whole diagnosis under SecureIbex:
  // alert_major_bus_o is a memory integrity (ECC) failure on the fetch
  // or load path, alert_major_internal_o is a lockstep comparator
  // mismatch. ORing them, as the first version of this file did, turns
  // "your testbench does not supply ECC check bits" and "the shadow
  // core disagrees with the main core" into the same message.
  reg saw_alert_minor     = 1'b0;
  reg saw_alert_major_int = 1'b0;
  reg saw_alert_major_bus = 1'b0;
  reg saw_double_fault = 1'b0;
  always @(posedge clk) begin
    if (rst_n) begin
      if (alert_minor)                             saw_alert_minor  <= 1'b1;
      if (alert_major_internal) saw_alert_major_int <= 1'b1;
      if (alert_major_bus)      saw_alert_major_bus <= 1'b1;
      if (double_fault_seen)                       saw_double_fault <= 1'b1;
    end
  end

  integer cycles = 0;
  always @(posedge clk) if (rst_n) cycles = cycles + 1;

  // Last fetch address, kept so a timeout can say WHERE it stopped
  // rather than only that it did. A hang in this system is always
  // "the program counter is somewhere unexpected", and the fetch
  // address is the cheapest observation of that -- no VCD, no
  // hierarchy reference into the core.
  reg [31:0] last_instr_addr = 32'hffff_ffff;
  reg [31:0] last_data_addr  = 32'hffff_ffff;
  always @(posedge clk) if (rst_n) begin
    if (dut.instr_req) last_instr_addr <= dut.instr_addr;
    if (dut.data_req)  last_data_addr  <= dut.data_addr;
  end

  // +trace prints the fetch address periodically. Off by default: it is
  // a debugging aid, not part of the pass criterion.
  always @(posedge clk)
    if (rst_n && $test$plusargs("trace") && (cycles % 20000 == 0))
      $display("[TB] cycle %0d  fetch=0x%08x  data=0x%08x",
               cycles, last_instr_addr, last_data_addr);

  integer i;
  integer errors = 0;

  initial begin
    for (i = 0; i < MEM_WORDS; i = i + 1) dut.mem[i] = 32'h0000_0000;
    // The image is linked at 0x80; 0x80/4 = 32 words in.
    $readmemh(`PROG_HEX, dut.mem, 32);

    if ($test$plusargs("vcd")) begin
      $dumpfile("tb_ibex_min.vcd");
      $dumpvars(0, tb_ibex_min);
    end

    $display("[TB] config: PMPEnable=%0d SecureIbex=%0d image=%s",
             `IBEX_PMPENABLE, `IBEX_SECUREIBEX, `PROG_HEX);

    repeat (20) @(posedge clk);
    rst_n = 1'b1;

    while (!halted && cycles < `TIMEOUT_CYCLES) @(posedge clk);

    if (!halted) begin
      $display("\n[TB] FAIL: timeout after %0d cycles without reaching halt",
               cycles);
      $display("[TB]   last fetch address 0x%08x, last data address 0x%08x",
               last_instr_addr, last_data_addr);
      $display("[TB]   trap_count=%0d mcause=0x%08x mepc=0x%08x",
               dut.mem[TRAP_COUNT_ADDR[31:2]],
               dut.mem[TRAP_MCAUSE_ADDR[31:2]],
               dut.mem[TRAP_MEPC_ADDR[31:2]]);
      errors = errors + 1;
    end else begin
      $display("\n[TB] halted after %0d cycles, exit code 0x%08x",
               cycles, exit_code);
      if (exit_code !== 32'h0) begin
        $display("[TB] FAIL: self-test reported failures, mask 0x%08x",
                 exit_code);
        errors = errors + 1;
      end
    end

    if (saw_alert_major_int) begin
      $display("[TB] FAIL: alert_major_internal_o asserted (lockstep mismatch)");
      errors = errors + 1;
    end
    if (saw_alert_major_bus) begin
      $display("[TB] FAIL: alert_major_bus_o asserted (memory integrity/ECC)");
      errors = errors + 1;
    end
    if (saw_double_fault) begin
      $display("[TB] FAIL: double_fault_seen_o asserted during the run");
      errors = errors + 1;
    end
    if (saw_alert_minor)
      $display("[TB] note: alert_minor asserted at least once");

    if (errors == 0) $display("[TB] PASS");
    else             $display("[TB] FAIL (%0d problems)", errors);

    $finish;
  end

endmodule
