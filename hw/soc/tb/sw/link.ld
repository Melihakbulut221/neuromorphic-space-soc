/* Bare-metal link map for tb/ibex_min_system.v.
 *
 * 16 KiB of unified RAM at 0. Ibex's reset vector is
 * {boot_addr_i[31:8], 8'h80} (rtl/ibex_if_stage.sv line 243), and the
 * testbench drives boot_addr_i = 0, so the first fetched instruction is
 * at 0x80 and .text must start there.
 *
 * The low 0x80 bytes are left unused rather than filled: nothing should
 * be reachable below the reset vector, and leaving the hole makes a
 * wild branch into it fetch zeros, which is an illegal instruction and
 * therefore a trap rather than silent nonsense.
 */

OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY {
  ram (rwx) : ORIGIN = 0x00000080, LENGTH = 16K - 0x80
}

SECTIONS {
  .text : {
    *(.text.start)
    *(.text .text.*)
  } > ram

  /* The trap vector needs 256-byte alignment because Ibex forces
     mtvec[7:2] to zero. It gets its OWN output section for that.
     Putting `.balign 256` into an input section of `.text` instead --
     including one named `.text.trapvec`, which the `*(.text .text.*)`
     wildcard above silently matches --
     raises `.text`'s own alignment to 256, and the linker then moves
     the whole section -- including `_start` -- from 0x80 up to 0x100.
     Ibex's reset vector is fixed at {boot_addr_i[31:8], 8'h80}, so the
     core went on fetching at 0x80, found the padding the linker had
     left there, took an illegal-instruction trap into a not-yet-set
     mtvec, and executed the program from arbitrary offsets. The
     symptom was garbled putchar output, not a crash. Hence the two
     ASSERTs at the end of this file. */
  .trapvec : { *(.trapvec) } > ram

  .rodata : { *(.rodata .rodata.*) } > ram

  .data : {
    /* gp anchors the +/-2 KiB gp-relative addressing window over the
       small-data sections; the linker's relaxation pass needs it to
       exist even though nothing here depends on the relaxation. */
    . = ALIGN(8);
    PROVIDE(__global_pointer$ = . + 0x800);
    *(.data .data.*)
    *(.sdata .sdata.*)
  } > ram

  .bss : {
    __bss_start = .;
    *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON)
    __bss_end = .;
  } > ram

  /* 64 bytes, aligned to 64. NAPOT regions must be NATURALLY aligned
     powers of two, and getting that wrong is silent and catastrophic
     rather than merely wrong: pmpaddr = (base >> 2) | 7 encodes "64
     bytes here" only if base is 64-aligned. At base 0x7e0 the same
     expression yields 0x1ff, whose nine trailing ones decode as a
     4096-byte region at 0x0 -- the whole image -- and with R-only
     permissions the core then took an instruction access fault on
     every fetch including the trap handler's own.

     `. = ALIGN(64);` OUTSIDE the section is not enough: the output
     section carries its own alignment attribute, which defaults to 1
     here, and the linker placed .pmpbuf immediately after .bss at
     0x7e0. The ALIGN goes INSIDE, where it moves the location counter
     within the section that is actually being emitted. */
  .pmpbuf (NOLOAD) : ALIGN(64) {
    . = ALIGN(64);
    __pmp_buf = .;
    . += 64;
  } > ram

  . = ALIGN(16);
  __stack_bottom = .;
  . = ORIGIN(ram) + LENGTH(ram);
  __stack_top = .;

  /DISCARD/ : { *(.comment) *(.note.*) *(.riscv.attributes) }
}

/* Both of these are silent-wrong-answer failures if they are violated,
   so they are checked at link time rather than discovered in a waveform. */
ASSERT(_start == 0x80,
       "_start must sit on Ibex's reset vector, {boot_addr_i[31:8], 8'h80}")
ASSERT((trap_vectors & 0xff) == 0,
       "trap_vectors must be 256-byte aligned: Ibex forces mtvec[7:2] to 0")
ASSERT(trap_vectors_end - trap_vectors == 128,
       "the 32-entry vector table must be exactly 128 bytes: one entry assembled compressed would put every later vector at the wrong offset")
ASSERT((__pmp_buf & 63) == 0,
       "__pmp_buf must be 64-byte aligned or the NAPOT encoding silently covers the image")
