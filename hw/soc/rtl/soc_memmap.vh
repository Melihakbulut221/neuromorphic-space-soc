// GENERATED FILE - edit regmap/memmap.yaml and run regmap/generate_memmap.py
//
// Address constants for the system fabric. BASE/MASK are a
// prefix-compare pair: the region is selected when
// (addr & MASK) == BASE. That is a correct decode only because
// every region is a naturally aligned power of two, which the
// generator enforces and sw/tests/test_memmap.py re-checks.
//
// DELIBERATELY NOT GUARDED with `ifndef. This file is a BODY of
// localparam declarations, included inside a module, and more
// than one module needs it. Verilog macro state is shared across
// every file in a compilation unit, so an include guard here
// would let the first module that includes it get the constants
// and silently give every later module an empty file. That is
// exactly what happened once: soc_top.v got the map and
// soc_bus.v got nothing, and the failure was an unbound-name
// error inside the address decoder with no hint of the cause.

localparam [31:0] SOC_BOOT_ADDR    = 32'hC0000000;
localparam [31:0] SOC_RESET_VECTOR = 32'hC0000080;

localparam [31:0] SOC_BASE_RAM      = 32'h00000000;
localparam [31:0] SOC_SIZE_RAM      = 32'h00008000;
localparam [31:0] SOC_MASK_RAM      = 32'hFFFF8000;
localparam [31:0] SOC_BASE_NPU      = 32'h10000000;
localparam [31:0] SOC_SIZE_NPU      = 32'h10000000;
localparam [31:0] SOC_MASK_NPU      = 32'hF0000000;
localparam [31:0] SOC_BASE_ROM      = 32'hC0000000;
localparam [31:0] SOC_SIZE_ROM      = 32'h00002000;
localparam [31:0] SOC_MASK_ROM      = 32'hFFFFE000;
localparam [31:0] SOC_BASE_QSPI3    = 32'hD0000000;
localparam [31:0] SOC_SIZE_QSPI3    = 32'h02000000;
localparam [31:0] SOC_MASK_QSPI3    = 32'hFE000000;
localparam [31:0] SOC_BASE_QSPI4    = 32'hD8000000;
localparam [31:0] SOC_SIZE_QSPI4    = 32'h08000000;
localparam [31:0] SOC_MASK_QSPI4    = 32'hF8000000;
localparam [31:0] SOC_BASE_CLINT    = 32'hE0000000;
localparam [31:0] SOC_SIZE_CLINT    = 32'h00010000;
localparam [31:0] SOC_MASK_CLINT    = 32'hFFFF0000;
localparam [31:0] SOC_BASE_PLIC     = 32'hF8000000;
localparam [31:0] SOC_SIZE_PLIC     = 32'h00400000;
localparam [31:0] SOC_MASK_PLIC     = 32'hFFC00000;
localparam [31:0] SOC_BASE_DEBUG    = 32'hFE000000;
localparam [31:0] SOC_SIZE_DEBUG    = 32'h01000000;
localparam [31:0] SOC_MASK_DEBUG    = 32'hFF000000;
localparam [31:0] SOC_BASE_APB      = 32'hFF900000;
localparam [31:0] SOC_SIZE_APB      = 32'h00100000;
localparam [31:0] SOC_MASK_APB      = 32'hFFF00000;
localparam [31:0] SOC_BASE_PNP      = 32'hFFFFF000;
localparam [31:0] SOC_SIZE_PNP      = 32'h00001000;
localparam [31:0] SOC_MASK_PNP      = 32'hFFFFF000;

localparam [31:0] SOC_APB_BASE = 32'hFF900000;
// APB slot index, compared against PADDR[19:12].
localparam [7:0] SOC_APBSLOT_UART0    = 8'h00;
localparam [7:0] SOC_APBSLOT_UART1    = 8'h01;
localparam [7:0] SOC_APBSLOT_GPIO     = 8'h02;
localparam [7:0] SOC_APBSLOT_TIMER0   = 8'h08;
localparam [7:0] SOC_APBSLOT_TIMER1   = 8'h09;
localparam [7:0] SOC_APBSLOT_SPW      = 8'h0D;
localparam [7:0] SOC_APBSLOT_CAN      = 8'h11;
localparam [7:0] SOC_APBSLOT_SPI      = 8'h12;
localparam [7:0] SOC_APBSLOT_I2C      = 8'h13;
localparam [7:0] SOC_APBSLOT_QSPICTL  = 8'h14;
localparam [7:0] SOC_APBSLOT_BUSSTAT  = 8'h15;
localparam [7:0] SOC_APBSLOT_SCRUB    = 8'h16;
localparam [7:0] SOC_APBSLOT_BOOTREG  = 8'h17;
localparam [7:0] SOC_APBSLOT_CLKGATE  = 8'h18;
localparam [7:0] SOC_APBSLOT_NPUCFG   = 8'h19;
localparam [7:0] SOC_APBSLOT_APBPNP   = 8'hFF;

// Ibex fast local interrupt index per source. This is the WIRE
// INDEX into irq_fast_i[14:0], not the plug-and-play source
// number: soc_top.v uses these to build the vector, and nothing
// in the RTL should ever write one down.
localparam integer SOC_IRQLINE_UART0    = 0;
localparam integer SOC_IRQLINE_UART1    = 1;
localparam integer SOC_IRQLINE_GPIO     = 2;
localparam integer SOC_IRQLINE_TIMER0   = 3;
localparam integer SOC_IRQLINE_TIMER1   = 4;
localparam integer SOC_IRQLINE_SPW      = 5;
localparam integer SOC_IRQLINE_CAN      = 6;
localparam integer SOC_IRQLINE_SPI      = 7;
localparam integer SOC_IRQLINE_I2C      = 8;
localparam integer SOC_IRQLINE_QSPICTL  = 9;
localparam integer SOC_IRQLINE_BUSSTAT  = 10;
localparam integer SOC_IRQLINE_SCRUB    = 11;
localparam integer SOC_IRQLINE_NPUCFG   = 12;

// Plug-and-play interrupt SOURCE NUMBER per peripheral. A block
// whose register map reports its own interrupt number -- GRLIB's
// GPTIMER configuration register does -- takes it from here, so
// the number a driver reads out of the peripheral and the number
// in the device table are the same number.
localparam [4:0] SOC_IRQNUM_UART0    = 5'd2;
localparam [4:0] SOC_IRQNUM_UART1    = 5'd3;
localparam [4:0] SOC_IRQNUM_GPIO     = 5'd4;
localparam [4:0] SOC_IRQNUM_TIMER0   = 5'd8;
localparam [4:0] SOC_IRQNUM_TIMER1   = 5'd12;
localparam [4:0] SOC_IRQNUM_SPW      = 5'd16;
localparam [4:0] SOC_IRQNUM_CAN      = 5'd18;
localparam [4:0] SOC_IRQNUM_SPI      = 5'd19;
localparam [4:0] SOC_IRQNUM_I2C      = 5'd20;
localparam [4:0] SOC_IRQNUM_QSPICTL  = 5'd21;
localparam [4:0] SOC_IRQNUM_BUSSTAT  = 5'd22;
localparam [4:0] SOC_IRQNUM_SCRUB    = 5'd23;
localparam [4:0] SOC_IRQNUM_NPUCFG   = 5'd24;

