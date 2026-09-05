// Icarus testbench for the whole SoC: Ibex, the fabric, the memory map.
//
// The difference from tb_ibex_min.v is the point of the exercise. That
// testbench WAS the memory system -- one flat array and two magic
// addresses. This one contains no model of anything the design does. It
// supplies a clock, a reset and a ROM image, and then observes:
//
//   * the serial line out of the console UART, which it decodes back
//     into characters. The program's output therefore travels the whole
//     path -- core, fabric, APB bridge, slot decode, UART register file,
//     baud divider, shift register -- and any break anywhere in it shows
//     up as garbled or missing text. Snooping the register write instead
//     would have proved the bridge and nothing after it.
//   * core_sleep_o, which is how the program says it has finished. The
//     frozen memory map has no "halt the simulator" address and this
//     testbench does not invent one; crt0.S leaves the exit code in RAM
//     and executes WFI.
//   * the alert outputs and double_fault_seen_o, latched, as
//     tb_ibex_min.v does.
//
// THE PASS CRITERION, and what it does not cover. A run passes only if
// ALL of these hold:
//
//   1. the core reached WFI, with the exit magic already posted in RAM,
//      before the timeout. The magic is part of the TERMINATION
//      condition and not only of the checks afterwards, because the SoC
//      can now reset its own core and Ibex reports core_sleep_o high
//      while it is held in reset -- so "awake, then asleep" alone goes
//      true in the middle of a watchdog reset;
//   2. the magic word beside the exit code says the exit code is
//      meaningful, so a WFI reached some other way is not mistaken for a
//      completed run;
//   3. the exit code is zero -- every self-check in the program passed;
//   4. the decoded serial stream contains "RESULT PASS", which is an
//      independent path to the same conclusion: criterion 3 reads RAM
//      through a hierarchical reference, criterion 4 reads the UART pin.
//      A fabric that corrupted peripheral writes would pass 3 and fail 4;
//      a program that lied about its own result would fail 3;
//   5. no alert asserted and double_fault_seen_o never asserted.
//
// It does NOT cover: any region or peripheral slot the map reserves and
// nothing implements (an access to one is checked as an error by the
// program, but nothing here checks that the reserved address is the
// right one); the fabric's behaviour under two masters contending, which
// this program exercises only as a by-product of running; anything at
// gate level; and any timing property at all. The cocotb suite in
// hw/soc/tb/cocotb/ is where the fabric is driven deliberately rather
// than incidentally.

`timescale 1ns / 1ps

`ifndef ROM_HEX
  `define ROM_HEX "test_ibex.hex"
`endif
`ifndef TIMEOUT_CYCLES
  `define TIMEOUT_CYCLES 5000000
`endif
// 8 * (scaler + 1) system clocks per bit, which is GRLIB's definition of
// the APBUART scaler: it feeds an 8x oversampling clock. The program
// programs the scaler from the same -D.
`ifndef UART_BIT_CYCLES
  `define UART_BIT_CYCLES 8
`endif
`ifndef EXIT_CODE_ADDR
  `define EXIT_CODE_ADDR 32'h0
`endif
`ifndef EXIT_MAGIC_ADDR
  `define EXIT_MAGIC_ADDR 32'h0
`endif
`ifndef TRAP_MCAUSE_ADDR
  `define TRAP_MCAUSE_ADDR 32'h0
`endif
`ifndef TRAP_MEPC_ADDR
  `define TRAP_MEPC_ADDR 32'h0
`endif
`ifndef TRAP_COUNT_ADDR
  `define TRAP_COUNT_ADDR 32'h0
`endif

module tb_soc;

  localparam integer CLK_HALF   = 5;     // 100 MHz, functional only
  localparam integer BIT_CYCLES = `UART_BIT_CYCLES;
  localparam integer BIT_TIME   = BIT_CYCLES * 2 * CLK_HALF;

  localparam [31:0] EXIT_CODE_ADDR  = `EXIT_CODE_ADDR;
  localparam [31:0] EXIT_MAGIC_ADDR = `EXIT_MAGIC_ADDR;
  localparam [31:0] TRAP_MCAUSE_ADDR = `TRAP_MCAUSE_ADDR;
  localparam [31:0] TRAP_MEPC_ADDR   = `TRAP_MEPC_ADDR;
  localparam [31:0] TRAP_COUNT_ADDR  = `TRAP_COUNT_ADDR;
  localparam [31:0] EXIT_MAGIC       = 32'h600d_c0de;

  reg clk   = 1'b0;
  reg rst_n = 1'b0;
  always #CLK_HALF clk = ~clk;

  wire uart_tx, uart_irq;
  wire wdog_n, wdog_rst, nmi, irq_timer, irq_soft, gptimer_irq;
  wire alert_minor, alert_major_internal, alert_major_bus;
  wire double_fault_seen, core_sleep;

  // -------------------------------------------------------------------
  // The GPIO pads and the board they are soldered to (docs/65).
  //
  // soc_top has no pad ring, so each pin leaves it as three wires --
  // what to drive, whether to drive, what the pad sees -- and the pad
  // is modelled HERE, as the one place outside the design where the
  // three meet. A pad whose output buffer is enabled shows the SoC's
  // own value; one whose buffer is disabled shows whatever the board
  // drives.
  //
  // The board is a loopback: pads 8..15 are wired to pads 0..7, so a
  // value the program drives on pin k arrives on pin k+8 as an INPUT.
  // That is what makes check 28 of the bring-up program a test of the
  // pin path rather than of a register: DATA reads back through the
  // pad model and the wire, never through the OUTPUT register, which
  // soc_gpio.v refuses to fold in for exactly this reason. Pins 0..7
  // are driven low by the board when the SoC does not drive them.
  //
  // Contention -- the SoC driving a looped-back pad against the pin it
  // is wired to, with a different value -- resolves to X, as it would
  // on a scope. The program never does it; a program that did would
  // read X out of DATA and fail its own check.
  // -------------------------------------------------------------------
  wire [15:0] gpio_o, gpio_oe, gpio_pad;
  wire        gpio_irq;
  genvar gp;
  generate
    for (gp = 0; gp < 8; gp = gp + 1) begin : g_pad
      assign gpio_pad[gp] = gpio_oe[gp] ? gpio_o[gp] : 1'b0;
      assign gpio_pad[gp + 8] = !gpio_oe[gp + 8]            ? gpio_pad[gp]
                              : (gpio_o[gp + 8] === gpio_pad[gp]) ? gpio_o[gp + 8]
                              : 1'bx;
    end
  endgenerate

  // The watchdog bootstrap pin is held LOW, which is the armed state.
  // A run with it high would have no watchdog at all and every watchdog
  // check in the program would pass vacuously, so it is a constant here
  // and hw/soc/tb/cocotb/test_soc_wdog.py is where the disabled case is
  // driven.
  soc_top #(.ROM_INIT(`ROM_HEX)) dut (
      .clk_i  (clk),
      .rst_ni (rst_n),
      .wdog_dis_i (1'b0),
      .uart_tx_o  (uart_tx),
      .uart_irq_o (uart_irq),
      .gpio_i     (gpio_pad),
      .gpio_o     (gpio_o),
      .gpio_oe_o  (gpio_oe),
      .gpio_irq_o (gpio_irq),
      .wdog_no       (wdog_n),
      .wdog_rst_o    (wdog_rst),
      .nmi_o         (nmi),
      .irq_timer_o   (irq_timer),
      .irq_soft_o    (irq_soft),
      .gptimer_irq_o (gptimer_irq),
      .alert_minor_o          (alert_minor),
      .alert_major_internal_o (alert_major_internal),
      .alert_major_bus_o      (alert_major_bus),
      .double_fault_seen_o    (double_fault_seen),
      .core_sleep_o           (core_sleep)
  );

  // -------------------------------------------------------------------
  // Latched alerts. They are pulses; a run must fail if one ever fired,
  // not only if one is firing at the end. Latched separately because
  // they mean different things: alert_major_bus_o is a memory integrity
  // failure, alert_major_internal_o is a lockstep mismatch. This build
  // has SecureIbex = 0, so neither should ever fire and either firing is
  // a real finding rather than a configuration artifact.
  // -------------------------------------------------------------------
  reg saw_alert_minor     = 1'b0;
  reg saw_alert_major_int = 1'b0;
  reg saw_alert_major_bus = 1'b0;
  reg saw_double_fault    = 1'b0;
  always @(posedge clk) if (rst_n) begin
    if (alert_minor)          saw_alert_minor     <= 1'b1;
    if (alert_major_internal) saw_alert_major_int <= 1'b1;
    if (alert_major_bus)      saw_alert_major_bus <= 1'b1;
    if (double_fault_seen)    saw_double_fault    <= 1'b1;
  end

  // "The core has run and then stopped", not "the core is not running".
  //
  // core_sleep_o is ALREADY HIGH while the core is held in reset -- a
  // core that is not fetching is not busy, and Ibex says so. Waiting on
  // core_sleep_o alone therefore returns instantly on the cycle reset is
  // released, and the run reports a timeout at whatever cycle count the
  // free-running counter had reached by the time the report is printed,
  // which is a symptom that points nowhere. The first version of this
  // file did exactly that. Requiring the core to have been observed
  // awake first is the whole fix.
  reg saw_awake = 1'b0;
  always @(posedge clk) if (rst_n && !core_sleep) saw_awake <= 1'b1;

  // AND the exit magic must already be in RAM.
  //
  // That third term was added when the watchdog arrived and it is not
  // belt and braces. The SoC can now reset its own core (soc_top.v's
  // reset section), and a core held in reset reports core_sleep_o high
  // -- so "awake, then asleep" becomes true in the middle of a watchdog
  // reset, tens of thousands of cycles before the program has finished.
  // The first watchdog run ended with the testbench reporting a timeout
  // at a cycle count that meant nothing, for exactly that reason.
  // Requiring the magic word makes the criterion "the program posted its
  // result and then slept", which is what was always meant.
  wire finished = saw_awake && core_sleep &&
                  (dut.u_ram.mem[EXIT_MAGIC_ADDR[31:2]] == EXIT_MAGIC);

  integer cycles = 0;
  always @(posedge clk) if (rst_n) cycles = cycles + 1;

  // -------------------------------------------------------------------
  // Watchdog escalation, reported as it happens.
  //
  // Not part of any pass criterion. It is here because every one of
  // these three events is invisible from the console -- stage 2 in
  // particular restarts the program, and without this line the symptom
  // is a log that simply begins again with no explanation. The first
  // watchdog bring-up run produced exactly that.
  // -------------------------------------------------------------------
  reg nmi_q = 1'b0, wdog_rst_q = 1'b0, wdog_n_q = 1'b1;
  integer wdog_stage1 = 0, wdog_stage2 = 0, wdog_stage3 = 0;
  always @(posedge clk) if (rst_n) begin
    if (nmi && !nmi_q) begin
      wdog_stage1 = wdog_stage1 + 1;
      $display("[TB] watchdog stage 1 (NMI) at cycle %0d", cycles);
    end
    if (wdog_rst && !wdog_rst_q) begin
      wdog_stage2 = wdog_stage2 + 1;
      $display("[TB] watchdog stage 2 (system reset) at cycle %0d", cycles);
    end
    if (!wdog_n && wdog_n_q) begin
      wdog_stage3 = wdog_stage3 + 1;
      $display("[TB] watchdog stage 3 (WDOGN pin) at cycle %0d", cycles);
    end
    nmi_q      <= nmi;
    wdog_rst_q <= wdog_rst;
    wdog_n_q   <= wdog_n;
  end

  // Last addresses seen on each master port, so a timeout can say WHERE
  // it stopped. A hang here is always "the program counter or a pointer
  // is somewhere unexpected", and these are the cheapest observation of
  // that -- no VCD, no reference inside the core.
  reg [31:0] last_instr_addr = 32'hffff_ffff;
  reg [31:0] last_data_addr  = 32'hffff_ffff;
  always @(posedge clk) if (rst_n) begin
    if (dut.instr_req && dut.instr_gnt) last_instr_addr <= dut.instr_addr;
    if (dut.data_req  && dut.data_gnt)  last_data_addr  <= dut.data_addr;
  end

  always @(posedge clk)
    if (rst_n && $test$plusargs("trace") && (cycles % 20000 == 0))
      $display("[TB] cycle %0d  fetch=0x%08x  data=0x%08x",
               cycles, last_instr_addr, last_data_addr);

  // +bustrace dumps every fabric handshake for the first BUSTRACE_CYCLES
  // cycles. Off by default and not part of any pass criterion: it is
  // here because a fabric stall is invisible from the outside -- the
  // symptom is a core that stops, with no clue which of the two masters
  // is waiting for what.
`ifndef BUSTRACE_CYCLES
  `define BUSTRACE_CYCLES 400
`endif
  always @(posedge clk)
    if (rst_n && $test$plusargs("bustrace") && cycles < `BUSTRACE_CYCLES)
      $display("[BUS] %0d I:%b%b%b %08x D:%b%b%b w%b %08x | req%b gnt%b rv%b | ci%0d/%0d cd%0d/%0d",
               cycles,
               dut.instr_req, dut.instr_gnt, dut.instr_rvalid, dut.instr_addr,
               dut.data_req, dut.data_gnt, dut.data_rvalid, dut.data_we,
               dut.data_addr,
               dut.s_req, dut.s_gnt, dut.s_rvalid,
               dut.u_bus.cnt_i, dut.u_bus.lock_i,
               dut.u_bus.cnt_d, dut.u_bus.lock_d);

  // -------------------------------------------------------------------
  // Serial receiver
  //
  // Start bit, eight data bits least significant first, one stop bit, no
  // parity -- what hw/soc/rtl/soc_uart.v transmits and what its header
  // documents. Sampling is at the middle of each bit: 1.5 bit times
  // after the falling edge of the start bit, then one bit time apart.
  //
  // The stop bit is checked. A framing error means the divider or the
  // shifter is wrong, and without the check that would show up only as
  // subtly wrong characters.
  // -------------------------------------------------------------------
  integer rx_chars = 0;
  integer rx_framing_errors = 0;
  reg [7:0] rx_byte;
  reg [87:0] rx_tail = 88'h0;      // last 11 characters
  reg rx_seen_pass = 1'b0;
  integer bit_i;

  initial begin
    @(posedge rst_n);
    // One clock so the UART's own reset has been applied and the line is
    // driven to its idle high before the first edge is looked for.
    @(posedge clk);
    forever begin
      @(negedge uart_tx);
      #(BIT_TIME + BIT_TIME / 2);
      for (bit_i = 0; bit_i < 8; bit_i = bit_i + 1) begin
        rx_byte[bit_i] = uart_tx;
        #(BIT_TIME);
      end
      // Now in the middle of the stop bit.
      if (uart_tx !== 1'b1) begin
        rx_framing_errors = rx_framing_errors + 1;
        $display("[TB] framing error after %0d characters", rx_chars);
      end
      rx_chars = rx_chars + 1;
      $write("%c", rx_byte);
      rx_tail = {rx_tail[79:0], rx_byte};
      if (rx_tail == "RESULT PASS") rx_seen_pass = 1'b1;
    end
  end

  // -------------------------------------------------------------------
  integer errors = 0;
  reg [31:0] exit_code, exit_magic;

  initial begin
    if ($test$plusargs("vcd")) begin
      $dumpfile("tb_soc.vcd");
      $dumpvars(0, tb_soc);
    end

    $display("[TB] SoC: boot 0x%08x, ROM image %s, %0d clocks per UART bit",
             dut.SOC_BOOT_ADDR, `ROM_HEX, BIT_CYCLES);

    repeat (20) @(posedge clk);
    rst_n = 1'b1;

    while (!finished && cycles < `TIMEOUT_CYCLES) @(posedge clk);

    // Let any character still in the shifter finish, so the log is not
    // truncated mid-word by the core going to sleep.
    #(BIT_TIME * 12);

    exit_code  = dut.u_ram.mem[EXIT_CODE_ADDR[31:2]];
    exit_magic = dut.u_ram.mem[EXIT_MAGIC_ADDR[31:2]];

    $display("");
    if (!finished) begin
      $display("[TB] FAIL: timeout after %0d cycles without reaching WFI", cycles);
      $display("[TB]   last fetch 0x%08x, last data 0x%08x",
               last_instr_addr, last_data_addr);
      $display("[TB]   trap_count=%0d mcause=0x%08x mepc=0x%08x",
               dut.u_ram.mem[TRAP_COUNT_ADDR[31:2]],
               dut.u_ram.mem[TRAP_MCAUSE_ADDR[31:2]],
               dut.u_ram.mem[TRAP_MEPC_ADDR[31:2]]);
      errors = errors + 1;
    end else begin
      $display("[TB] core asleep after %0d cycles", cycles);
      if (exit_magic !== EXIT_MAGIC) begin
        $display("[TB] FAIL: exit magic 0x%08x, expected 0x%08x: the core slept without finishing",
                 exit_magic, EXIT_MAGIC);
        errors = errors + 1;
      end else if (exit_code !== 32'h0) begin
        $display("[TB] FAIL: self-test reported failures, mask 0x%08x", exit_code);
        errors = errors + 1;
      end else begin
        $display("[TB] exit code 0x%08x", exit_code);
      end
    end

    $display("[TB] console: %0d characters decoded, %0d framing errors",
             rx_chars, rx_framing_errors);
    $display("[TB] watchdog: stage1 %0d, stage2 %0d, stage3 %0d",
             wdog_stage1, wdog_stage2, wdog_stage3);
    $display("[TB] gpio: pads 0x%04x, driven 0x%04x, irq %b",
             gpio_pad, gpio_oe, gpio_irq);
    if (rx_chars == 0) begin
      $display("[TB] FAIL: nothing came out of the UART");
      errors = errors + 1;
    end
    if (rx_framing_errors != 0) begin
      $display("[TB] FAIL: %0d framing errors on the console line",
               rx_framing_errors);
      errors = errors + 1;
    end
    if (!rx_seen_pass) begin
      $display("[TB] FAIL: \"RESULT PASS\" never appeared on the console line");
      errors = errors + 1;
    end

    if (saw_alert_major_int) begin
      $display("[TB] FAIL: alert_major_internal_o asserted (lockstep mismatch)");
      errors = errors + 1;
    end
    if (saw_alert_major_bus) begin
      $display("[TB] FAIL: alert_major_bus_o asserted (memory integrity)");
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
