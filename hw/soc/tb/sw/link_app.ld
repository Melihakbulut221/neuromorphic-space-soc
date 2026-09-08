/* SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut */
/* SPDX-License-Identifier: Apache-2.0 */

/* Bare-metal link map for the APPLICATION (hw/soc/tb/sw/test_ibex.c)
 * once it is a flash image loaded into RAM rather than a ROM resident,
 * docs/68.
 *
 * WHAT CHANGED FROM link_soc.ld, AND WHAT DID NOT.
 *
 * Everything is in RAM: .text, the trap vector table, .rodata, .data,
 * .bss, the PMP buffer and the stack. There is no ROM in this map at
 * all -- the ROM belongs to the loader (link_boot.ld) and this program
 * never fetches from it.
 *
 * .data IS STILL A SEPARATE OUTPUT SECTION WITH A LOAD ADDRESS, and the
 * load address is now equal to the run address. That is deliberate and
 * it is why crt0.S is UNCHANGED: its relocation loop still runs, still
 * copies __data_end - __data_start bytes, and copies them onto
 * themselves. Deleting the loop would have been a change to the program
 * whose cycle count docs/66 published, and the whole point of loading
 * the same program from a different place is that the program is the
 * same program. What the loop costs is therefore identical in both
 * builds and the cycle difference between them is attributable to the
 * fabric alone (docs/68 section 8).
 *
 * _start is at the base of the RAM region, not at Ibex's reset vector:
 * the core never resets into this image, the loader jumps into it. The
 * ASSERT below is the link_soc.ld assert with the other constant.
 *
 * THE IMAGE THIS PRODUCES IS THE FLASH IMAGE. `objcopy -O binary` over
 * this link is exactly the bytes the loader copies to `LOAD`, and
 * hw/soc/flow/gen_boot_image.py takes the load address, the entry point
 * and the length out of the ELF rather than being told them, so a
 * program that moved cannot be loaded to where it used to be.
 */

INCLUDE memmap.ld

OUTPUT_ARCH(riscv)
ENTRY(_start)

SECTIONS {
  .text __soc_ram_base : {
    *(.text.start)
    *(.text .text.*)
  } > ram

  .trapvec : { *(.trapvec) } > ram

  .rodata : {
    . = ALIGN(4);
    *(.rodata .rodata.*)
    . = ALIGN(4);
  } > ram

  /* The ALIGN is OUTSIDE the section, not inside it. Inside, it is
     padding within the section and LOADADDR(.data) is still the
     section's own start, so __data_load and __data_start differ by the
     padding and crt0.S's relocation loop copies from the wrong place --
     which on this link, where the two are equal, would have been
     invisible until the padding was non-zero. Outside, the section
     starts where __data_start does. */
  . = ALIGN(8);
  .data : {
    PROVIDE(__global_pointer$ = . + 0x800);
    __data_start = .;
    *(.data .data.*)
    *(.sdata .sdata.*)
    . = ALIGN(4);
    __data_end = .;
  } > ram

  __data_load = LOADADDR(.data);

  /* The end of the image the loader copies. Everything above this is
     .bss, the PMP buffer and the stack, and NONE of it is in the image
     -- which is exactly why the loader's RAM sweep has to exist: those
     words are never written by the loader and their check bits would
     otherwise be whatever the SRAM powered up with. docs/68 section 4. */
  __image_end = .;

  .bss (NOLOAD) : {
    . = ALIGN(4);
    __bss_start = .;
    *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON)
    . = ALIGN(4);
    __bss_end = .;
  } > ram

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

ASSERT(_start == __soc_ram_base,
       "_start must sit at the base of the RAM region: that is what the image header's ENTRY says and what the loader jumps to")
ASSERT((trap_vectors & 0xff) == 0,
       "trap_vectors must be 256-byte aligned: Ibex forces mtvec[7:2] to 0")
ASSERT(trap_vectors_end - trap_vectors == 128,
       "the 32-entry vector table must be exactly 128 bytes")
ASSERT((__pmp_buf & 63) == 0,
       "__pmp_buf must be 64-byte aligned or the NAPOT encoding silently covers more")
ASSERT(LOADADDR(.data) == ADDR(.data),
       "the application image is position-fixed: .data must load where it runs")
ASSERT(__data_load == __data_start,
       "the ALIGN before .data must leave the section starting at __data_start, or crt0.S's relocation loop copies from the wrong address")
ASSERT(__stack_bottom <= __stack_top,
       "RAM is full: the image, .bss and the PMP buffer leave no room for a stack")
