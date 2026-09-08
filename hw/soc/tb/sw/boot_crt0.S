// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: Apache-2.0

// Startup for the BOOT LOADER, docs/68.
//
// The sibling crt0.S is the application's, and the two are deliberately
// separate files rather than one file with a third `#ifdef`: crt0.S
// carries a 32-entry vector table, four interrupt stubs, a keyed
// watchdog acknowledge and a trap-storm guard, none of which a loader
// has any use for, and every byte of it would come out of the 8,064
// bytes of ROM the loader has to fit in.
//
// =====================================================================
// THE FIRST THING THIS FILE DOES IS WRITE EVERY WORD OF THE RAM
// =====================================================================
//
// docs/67 put a SECDED check field on every row of the RAM. On this PDK
// the RAM is an SRAM and an SRAM POWERS UP UNDEFINED -- and so does its
// check field. A word nothing has written is therefore NOT a zero: it
// is a random 32 bits beside a random check field, and the codec's
// answer to it is an UNCORRECTABLE, which soc_mem_ecc.v answers with a
// bus error and the core takes as a load access fault.
//
// That is the same class of problem as the boot ROM's contents, one
// memory across, and it has the same shape: check bits nobody has
// initialised are check bits nobody can read. The difference is that
// the RAM has something that can write it, and this is that something.
//
// THE SWEEP WRITES WHOLE WORDS, and that word is load-bearing. A RAM
// row holds four independent (16,8) byte codewords (docs/67 section
// 3.3) and a byte write updates one lane's data AND its eight check
// bits together through the macro's own A_BM. So:
//
//   * a WORD store makes all four lanes of that word valid at once;
//   * a BYTE store makes ONE lane valid and leaves the other three as
//     they powered up -- and a later 32-bit load of that word reads all
//     four lanes and gets an uncorrectable from the three nobody wrote.
//
// A loader that initialised the RAM a byte at a time would therefore
// leave it in exactly the state it was trying to leave behind. The
// counterfactual builds -DBOOT_NO_SWEEP and -DBOOT_SWEEP_BYTE exist to
// measure both halves of that: docs/68 section 4.
//
// IT RUNS BEFORE THE STACK POINTER IS SET, and that is not an accident
// of ordering -- it is the only order that works. The loader's stack,
// its .data and its .bss are all in the RAM this loop is initialising,
// so nothing that needs any of them may run first. The loop uses three
// registers and no memory reads at all.
//
// It costs one store per word: 8,192 stores for the 32 KiB map. docs/68
// section 8 measures what that is in cycles and compares it with the
// watchdog's budget.

#include "soc_memmap.h"
#include "soc_timers.h"

  .section .text.start, "ax"
  .global _start
  .option norvc                 // keep the reset sequence 32-bit so the
                                // entry point is readable in a hexdump
_start:
  // mtvec first, so that a fault anywhere below lands somewhere known.
  // Ibex forces mtvec[7:2] to zero and has no direct mode; the table is
  // in the ROM and the link script asserts its alignment and its size.
  la    t0, boot_trap_vectors
  csrw  mtvec, t0

  // ---- the RAM sweep. See the header. ------------------------------
  li    t0, SOC_RAM_BASE
  li    t1, SOC_RAM_BASE + SOC_RAM_SIZE
#if defined(BOOT_NO_SWEEP)
  // COUNTERFACTUAL: no sweep at all. What a loader that has not been
  // told about the check bits does. docs/68 section 4.
#elif defined(BOOT_SWEEP_BYTE)
  // COUNTERFACTUAL: a sweep that writes BYTES. It initialises one of
  // the four byte codewords of every word and leaves three as the SRAM
  // powered up, so the first 32-bit load of any of them is an
  // uncorrectable. This is the build that shows that "initialise the
  // RAM" is not the requirement -- "write whole codewords" is.
1:
  sb    zero, 0(t0)
  addi  t0, t0, 4
  bltu  t0, t1, 1b
#else
1:
  sw    zero, 0(t0)
  addi  t0, t0, 4
  bltu  t0, t1, 1b
#endif

  // Only now is there a RAM that can be read.
  la    sp, __boot_stack_top
  la    gp, __global_pointer$

  // .bss needs no zeroing loop: the sweep above wrote every word of the
  // RAM, which includes all of it. The symbols exist so that
  // boot.c can assert the sweep covered them.

  // Relocate .data from the ROM to the loader's private RAM.
  la    t0, __data_load
  la    t1, __data_start
  la    t2, __data_end
2:
  bgeu  t1, t2, 3f
  lw    t3, 0(t0)
  sw    t3, 0(t1)
  addi  t0, t0, 4
  addi  t1, t1, 4
  j     2b
3:

  // boot_main returns the entry point of the image it loaded. Every
  // path that cannot load one ends INSIDE boot_main, in the escalation
  // of docs/68 section 6, so a return is always a success.
  //
  // THE GUARD IS A RANGE AND NOT A ZERO TEST. The application is linked
  // to the base of the RAM, so its entry point is 0x00000000 and a
  // `beqz` here rejects every good boot -- which is the defect the
  // first whole-SoC run of this loader found one level up, in
  // boot.c's try_image. What is actually impossible is an entry outside
  // the RAM, and that is what is tested: a boot_main that fell off its
  // end lands on a named spin rather than on whatever a0 held.
  call  boot_main
  li    t0, SOC_RAM_BASE + SOC_RAM_SIZE
  bgeu  a0, t0, boot_no_entry

  // ---- the hand-over ----------------------------------------------
  //
  // The loader's job ends here. It does NOT tidy up: the image's own
  // _start sets its own mtvec, its own stack pointer and its own gp,
  // and every byte of RAM the loader was using below __boot_private is
  // already the image's. What it must NOT do is leave an interrupt
  // enabled that the image is not ready for -- the loader never enables
  // one (mstatus.MIE is zero out of reset and nothing here sets it) and
  // the one line it uses, the QSPI controller's, it drives by polling.
  jr    a0

boot_no_entry:
  j     boot_no_entry

  .option rvc

// ---------------------------------------------------------------------
// The loader's trap table.
//
// Thirty-two four-byte entries, as the application's is and for the same
// reason: Ibex vectors interrupts at mtvec + 4*id and a compressed jump
// would put every later entry at the wrong offset.
//
// It is much smaller than the application's in what it DOES. The loader
// enables no interrupt, so every maskable entry is a spin; the NMI entry
// is a spin ON PURPOSE, because the loader's whole escalation is "stop
// kicking and let the watchdog do its job" and a stage-1 handler that
// acknowledged would postpone stage 2 for another full timeout.
//
// The SYNCHRONOUS entry is the one that does work, and it is the reason
// this table exists at all. The loader reads back everything it wrote
// into the RAM (boot.c's verify pass), and a word that is not a codeword
// answers with a bus error, which arrives as a LOAD ACCESS FAULT. That
// is not a failure of the loader; it is the loader finding an
// uncorrectable in the image it just loaded, which is one of the four
// things docs/68 section 6 has to escalate. So the handler records the
// cause, steps over the faulting instruction and returns, and boot.c
// checks the flag rather than the fault taking the machine down.
// ---------------------------------------------------------------------
  .section .trapvec, "ax"
  .balign 256
  .option push
  .option norvc
  .global boot_trap_vectors
boot_trap_vectors:
  j     boot_trap_entry   //  0  every synchronous exception
  j     boot_spin         //  1
  j     boot_spin         //  2
  j     boot_spin         //  3
  j     boot_spin         //  4
  j     boot_spin         //  5
  j     boot_spin         //  6
  j     boot_spin         //  7
  j     boot_spin         //  8
  j     boot_spin         //  9
  j     boot_spin         // 10
  j     boot_spin         // 11
  j     boot_spin         // 12
  j     boot_spin         // 13
  j     boot_spin         // 14
  j     boot_spin         // 15
  j     boot_spin         // 16
  j     boot_spin         // 17
  j     boot_spin         // 18
  j     boot_spin         // 19
  j     boot_spin         // 20
  j     boot_spin         // 21
  j     boot_spin         // 22
  j     boot_spin         // 23
  j     boot_spin         // 24
  j     boot_spin         // 25
  j     boot_spin         // 26
  j     boot_spin         // 27
  j     boot_spin         // 28
  j     boot_spin         // 29
  j     boot_spin         // 30
  j     boot_nmi          // 31  watchdog stage 1
  .global boot_trap_vectors_end
boot_trap_vectors_end:
  .option pop

// The loader enables nothing maskable, so reaching one of these means
// a line came up that nothing asked for. Spin: the watchdog is the
// backstop and this is exactly the case it exists for.
boot_spin:
  j     boot_spin

// Watchdog stage 1. DELIBERATELY NOT ACKNOWLEDGED -- see the table's
// comment. A loader that is not making progress should be reset, and
// this is the entry that lets that happen.
boot_nmi:
  j     boot_nmi

// ---------------------------------------------------------------------
// Synchronous exceptions.
//
// Record the cause and the PC, count it, step over the faulting
// instruction and return. The loader's own loads and stores are all
// 32-bit (it is compiled with -march=rv32imc but every access it makes
// to the image is a word), so mepc advances by the instruction's own
// width, read from the instruction itself exactly as crt0.S does.
//
// The runaway guard is crt0.S's, with a much lower ceiling: a loader
// that has taken sixteen faults is not going to load an image, and
// spinning here is the right answer because the watchdog is what ends
// it. boot.c never lets it get that far -- it checks boot_fault_count
// after the verify pass and gives up on the image at the first one.
// ---------------------------------------------------------------------
  .global boot_trap_entry
boot_trap_entry:
  addi  sp, sp, -32
  sw    t0, 0(sp)
  sw    t1, 4(sp)
  sw    t2, 8(sp)

  csrr  t0, mcause
  la    t1, boot_fault_cause
  sw    t0, 0(t1)

  csrr  t0, mepc
  la    t1, boot_fault_pc
  sw    t0, 0(t1)

  la    t1, boot_fault_count
  lw    t2, 0(t1)
  addi  t2, t2, 1
  sw    t2, 0(t1)

  li    t1, 16
  bgeu  t2, t1, boot_spin

  lhu   t2, 0(t0)
  andi  t2, t2, 3
  li    t1, 3
  beq   t2, t1, 4f
  addi  t0, t0, 2
  j     5f
4:
  addi  t0, t0, 4
5:
  csrw  mepc, t0

  lw    t0, 0(sp)
  lw    t1, 4(sp)
  lw    t2, 8(sp)
  addi  sp, sp, 32
  mret

  .section .bss
  .align 4
  .global boot_fault_cause
  .global boot_fault_pc
  .global boot_fault_count
boot_fault_cause: .word 0
boot_fault_pc:    .word 0
boot_fault_count: .word 0
