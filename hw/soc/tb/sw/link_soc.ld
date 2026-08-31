/* Bare-metal link map for the real SoC (hw/soc/rtl/soc_top.v).
 *
 * The sibling link.ld targets the minimal testbench memory of docs/38:
 * one flat RAM at 0, everything in it. This one targets the frozen
 * memory map, which is a different and more demanding thing:
 *
 *   .text, .rodata and the trap vector live in the boot ROM at
 *   0xC0000080, so every instruction fetch crosses the fabric to the ROM
 *   slave and every string literal is a data read from that same slave;
 *
 *   .data, .bss, the stack and the PMP buffer live in RAM at 0, so every
 *   data write crosses to a different slave;
 *
 *   .data is loaded in the ROM and relocated by crt0.S at startup, which
 *   is the first thing the program does and therefore the first thing
 *   that would break if the two regions were decoded the same way.
 *
 * The MEMORY block is NOT written here. It is INCLUDEd from memmap.ld,
 * which regmap/generate_memmap.py emits from regmap/memmap.yaml. That is
 * deliberate: docs/38 section 7.5 defect 4 was a link-time accident that
 * moved _start off Ibex's fixed reset vector and cost a debugging
 * session, and the cheapest defence is that no human writes the reset
 * vector down twice. Build with -L pointing at this directory.
 */

INCLUDE memmap.ld

OUTPUT_ARCH(riscv)
ENTRY(_start)

SECTIONS {
  .text : {
    *(.text.start)
    *(.text .text.*)
  } > rom

  /* Its own output section, for the reason link.ld's comment gives at
     length: `.balign 256` inside an input section of `.text` raises the
     whole output section's alignment and moves _start. Ibex forces
     mtvec[7:2] to zero, so this section must be 256-byte aligned and
     must not drag anything with it. */
  .trapvec : { *(.trapvec) } > rom

  .rodata : {
    . = ALIGN(4);
    *(.rodata .rodata.*)
    . = ALIGN(4);
  } > rom

  /* Run in RAM, loaded from ROM. crt0.S copies between the two. */
  .data : {
    . = ALIGN(8);
    /* gp anchors the +/-2 KiB gp-relative window over the small-data
       sections; the linker's relaxation pass needs it to exist. */
    PROVIDE(__global_pointer$ = . + 0x800);
    __data_start = .;
    *(.data .data.*)
    *(.sdata .sdata.*)
    . = ALIGN(4);
    __data_end = .;
  } > ram AT> rom

  __data_load = LOADADDR(.data);

  .bss (NOLOAD) : {
    . = ALIGN(4);
    __bss_start = .;
    *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON)
    . = ALIGN(4);
    __bss_end = .;
  } > ram

  /* 64 bytes, aligned to 64, INSIDE the section -- see link.ld for the
     full account of why the ALIGN goes here and not outside. A NAPOT
     region whose base is not naturally aligned does not encode a
     slightly wrong region, it encodes a much larger one. */
  .pmpbuf (NOLOAD) : ALIGN(64) {
    . = ALIGN(64);
    __pmp_buf = .;
    . += 64;
  } > ram

  . = ALIGN(16);
  __stack_bottom = .;
  . = __soc_ram_top;
  __stack_top = .;

  /DISCARD/ : { *(.comment) *(.note.*) *(.riscv.attributes) }
}

/* Every one of these is a silent-wrong-answer failure if violated, so
   they are link-time errors rather than waveform archaeology. The first
   is the one that actually happened once. */
ASSERT(_start == __soc_reset_vector,
       "_start must sit on Ibex's reset vector, {boot_addr_i[31:8], 8'h80}")
ASSERT((trap_entry & 0xff) == 0,
       "trap_entry must be 256-byte aligned: Ibex forces mtvec[7:2] to 0")
ASSERT((__pmp_buf & 63) == 0,
       "__pmp_buf must be 64-byte aligned or the NAPOT encoding silently covers more")
ASSERT(__stack_bottom <= __stack_top,
       "RAM is full: .data, .bss and the PMP buffer leave no room for a stack")
