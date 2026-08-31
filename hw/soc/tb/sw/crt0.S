// Startup and trap handler for the Ibex bring-up test.
//
// Deliberately tiny: this exists to get from Ibex's reset vector into C
// and to catch traps, nothing more. It is not the S2 supervisor
// (docs/09 part B track 3) and is not intended to become it.
//
// TWO PLATFORMS, ONE FILE. Without SOC_PLATFORM this is the bring-up
// program of docs/38: one flat RAM at 0, a magic store address that
// halts the testbench. With -DSOC_PLATFORM it targets the real SoC of
// docs/39-soc-bus-and-memory-map.md: .text in the boot ROM, .data
// relocated to RAM at startup, and termination by WFI with the exit code
// left in RAM, because the frozen memory map has no address whose
// meaning is "stop the simulator" and inventing one would put a
// testbench artifact into a map that is supposed to describe silicon.
//
// The two paths are kept in one file on purpose: the reset sequence, the
// mtvec constraint and the trap handler are properties of the CORE, not
// of the platform, and duplicating them would let one copy drift.

  .section .text.start, "ax"
  .global _start
  .option norvc                 // keep the reset sequence 32-bit so the
                                // entry point is readable in a hexdump
_start:
  // mtvec. Two Ibex-specific constraints, both stricter than the
  // RISC-V privileged spec's, both from
  // ext/ibex/doc/03_reference/cs_registers.rst and confirmed in
  // ext/ibex/rtl/ibex_cs_registers.sv and ibex_if_stage.sv:
  //
  //   * BASE is ALWAYS 256-byte aligned -- mtvec[7:2] reads as zero
  //     regardless of what is written, and ibex_if_stage.sv line 231
  //     forms the exception PC as {csr_mtvec_i[31:8], 8'h00}. A
  //     4-byte-aligned handler, which the spec permits, is silently
  //     truncated to the enclosing 256-byte boundary and the core
  //     vectors into whatever happens to live there. That is what the
  //     first version of this file did: every trap jumped into the
  //     middle of unrelated code, faulted again, and the run showed up
  //     as double_fault_seen_o plus a timeout with no other symptom.
  //   * MODE is hardwired to 2'b01 (vectored) and is read-only. Ibex
  //     has no direct mode. Synchronous exceptions still enter at BASE
  //     itself, which is all this program needs; interrupts would
  //     enter at BASE + 4*cause, and this handler is not a vector
  //     table, so nothing here may enable interrupts.
  la    t0, trap_entry
  csrw  mtvec, t0

  la    sp, __stack_top
  la    gp, __global_pointer$

  // zero .bss
  la    t0, __bss_start
  la    t1, __bss_end
1:
  bgeu  t0, t1, 2f
  sw    zero, 0(t0)
  addi  t0, t0, 4
  j     1b
2:

#ifdef SOC_PLATFORM
  // Relocate .data from its load address in the boot ROM to its run
  // address in RAM. This exists only on the SoC platform, and its
  // existence is itself a check on the memory map: the copy reads
  // through the ROM slave and writes through the RAM slave, so a decode
  // that sent one of them to the wrong place would corrupt every
  // initialised variable in the program before main is entered.
  la    t0, __data_load
  la    t1, __data_start
  la    t2, __data_end
4:
  bgeu  t1, t2, 5f
  lw    t3, 0(t0)
  sw    t3, 0(t1)
  addi  t0, t0, 4
  addi  t1, t1, 4
  j     4b
5:
#endif

  call  main

#ifdef SOC_PLATFORM
  // Terminate by sleeping. The exit code goes to a known word in RAM and
  // the magic beside it says the word is meaningful, so a run that
  // wandered into WFI some other way cannot be mistaken for a completed
  // one. The testbench watches core_sleep_o and then reads both.
  la    t0, exit_code
  sw    a0, 0(t0)
  la    t0, exit_magic
  li    t1, 0x600dc0de
  sw    t1, 0(t0)
  fence
3:
  wfi
  j     3b
#else
  // main returns the exit code; hand it to the testbench.
  li    t0, 0x00100004
  sw    a0, 0(t0)
3:
  j     3b
#endif

  .option rvc

// ---------------------------------------------------------------------
// Trap handler.
//
// Records mcause and mepc in globals, sets a flag, and resumes at
// mepc + the width of the faulting instruction. The tests that trap on
// purpose all use .option norvc around the faulting instruction, so the
// width is 4; the handler asserts that rather than assuming it, by
// checking the low two bits of the instruction it is about to skip.
// If a compressed instruction ever traps, trap_saw_rvc goes non-zero
// and the C code fails the run instead of silently resuming in the
// middle of an instruction.
// ---------------------------------------------------------------------
  // Section name deliberately NOT .text.something: the linker script's
  // `*(.text .text.*)` wildcard matches `.text.trapvec`, so a name in
  // that family gets pulled back into .text and drags its 256-byte
  // alignment onto the whole section, which moves _start off the reset
  // vector. See the comment in link.ld.
  .section .trapvec, "ax"
  // 256, not 4: see the mtvec note in _start. .balign takes bytes.
  .balign 256
  .global trap_entry
trap_entry:
  addi  sp, sp, -32
  sw    t0, 0(sp)
  sw    t1, 4(sp)
  sw    t2, 8(sp)

  csrr  t0, mcause
  la    t1, trap_mcause
  sw    t0, 0(t1)

  csrr  t0, mepc
  la    t1, trap_mepc
  sw    t0, 0(t1)

  la    t1, trap_count
  lw    t2, 0(t1)
  addi  t2, t2, 1
  sw    t2, 0(t1)

  // Runaway guard. The first version of this handler could enter an
  // unbounded trap loop (a 32-bit illegal instruction whose low two
  // bits looked compressed, so mepc advanced by 2 into the middle of
  // itself). That showed up only as a simulation timeout, which says
  // nothing about where it happened. Past 64 traps the run is over:
  // halt the testbench with a distinct code instead of hanging.
  li    t1, 64
  bltu  t2, t1, trap_continue
#ifdef SOC_PLATFORM
  la    t0, exit_code
  li    t1, 0xdead0001            // "trap storm"
  sw    t1, 0(t0)
  la    t0, exit_magic
  li    t1, 0x600dc0de
  sw    t1, 0(t0)
  fence
0:
  wfi
  j     0b
#else
  li    t0, 0x00100004
  li    t1, 0xdead0001            // "trap storm"
  sw    t1, 0(t0)
0:
  j     0b
#endif
trap_continue:

  // Look at the faulting instruction: (insn & 3) == 3 means 32-bit.
  lhu   t2, 0(t0)
  andi  t2, t2, 3
  li    t1, 3
  beq   t2, t1, 4f
  // compressed: record it and skip 2 so we still make progress
  la    t1, trap_saw_rvc
  li    t2, 1
  sw    t2, 0(t1)
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
  .global trap_mcause
  .global trap_mepc
  .global trap_count
  .global trap_saw_rvc
trap_mcause:   .word 0
trap_mepc:     .word 0
trap_count:    .word 0
trap_saw_rvc:  .word 0
#ifdef SOC_PLATFORM
  .global exit_code
  .global exit_magic
exit_code:     .word 0
exit_magic:    .word 0
#endif
