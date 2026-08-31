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

#ifdef SOC_PLATFORM
// For the watchdog acknowledge in the NMI handler. This is a .S file, so
// the C preprocessor runs over it and the same header the C code uses
// supplies the same constants -- there is no second copy of the key or
// of WDOGSTAT's address.
#include "soc_timers.h"
#endif

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
  //     has no direct mode. Synchronous exceptions enter at BASE
  //     itself; INTERRUPTS enter at BASE + 4*cause.
  //
  // Until docs/40-interrupts-timers-watchdog.md there was nothing in
  // this SoC that could raise an interrupt, so this program installed a
  // single handler and the second constraint was never exercised -- the
  // core only ever entered at BASE. There is now a real vector table
  // below and the tests in test_ibex.c check the entry point of every
  // interrupt they take, so a wrong vector is a reported failure and not
  // a jump into whatever follows.
  la    t0, trap_vectors
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

// ---------------------------------------------------------------------
// The vector table.
//
// Thirty-two entries of exactly four bytes, at offsets 0x00..0x7C, which
// is what Ibex's exception PC arithmetic demands and what the generated
// map records: soc_memmap.h's SOC_VEC_* are 4*id and SOC_VECTOR_BYTES is
// 128. `.option norvc` around the whole table is load-bearing -- a
// compressed jump would be two bytes and every entry after it would be
// at the wrong offset, which is a failure that looks like the core
// vectoring at random.
//
// Entry 0 is where EVERY synchronous exception enters, because Ibex
// forms the exception PC as {mtvec[31:8], 8'h00} for those and only
// vectors interrupts. Entries 1, 2 and 4..15 other than 3, 7 and 11 have
// no source in this SoC and go to a handler that records that fact
// instead of falling through into the next entry.
//
// Each USED entry has its own stub, and each stub writes a distinct
// marker before joining the common handler. That is deliberate: the
// marker says which VECTOR the core entered at and mcause says which
// interrupt the core THINKS it took, and comparing the two is the only
// way a wrong vector is distinguishable from a right one. Reading mcause
// alone would prove nothing about the vectoring.
// ---------------------------------------------------------------------
  .option push
  .option norvc
  .global trap_vectors
trap_vectors:
  j     trap_entry        //  0  synchronous exceptions, all of them
  j     vec_spurious      //  1
  j     vec_spurious      //  2
  j     vec_msoft         //  3  machine software, CLINT msip
  j     vec_spurious      //  4
  j     vec_spurious      //  5
  j     vec_spurious      //  6
  j     vec_mtimer        //  7  machine timer, CLINT mtimecmp
  j     vec_spurious      //  8
  j     vec_spurious      //  9
  j     vec_spurious      // 10
  j     vec_spurious      // 11  machine external: no PLIC, tied low
  j     vec_spurious      // 12
  j     vec_spurious      // 13
  j     vec_spurious      // 14
  j     vec_spurious      // 15
  j     vec_fast0         // 16  fast line 0, UART0
  j     vec_spurious      // 17
  j     vec_spurious      // 18
  j     vec_fast3         // 19  fast line 3, GPTIMER0
  j     vec_spurious      // 20
  j     vec_spurious      // 21
  j     vec_spurious      // 22
  j     vec_spurious      // 23
  j     vec_spurious      // 24
  j     vec_spurious      // 25
  j     vec_spurious      // 26
  j     vec_spurious      // 27
  j     vec_spurious      // 28
  j     vec_spurious      // 29
  j     vec_spurious      // 30
  j     vec_nmi           // 31  non-maskable: watchdog stage 1
  .global trap_vectors_end
trap_vectors_end:
  .option pop

// ---------------------------------------------------------------------
// Interrupt stubs.
//
// t0 carries the marker. Nothing else is touched before irq_common
// saves, so the stub costs two instructions and no stack.
// ---------------------------------------------------------------------
vec_spurious: li t0, 0xFF ; j irq_common
vec_msoft:    li t0, 3    ; j irq_common
vec_mtimer:   li t0, 7    ; j irq_common
vec_fast0:    li t0, 16   ; j irq_common
vec_fast3:    li t0, 19   ; j irq_common

// ---------------------------------------------------------------------
// Common maskable-interrupt handler.
//
// It does NOT clear the interrupt source -- it MASKS it, by clearing the
// source's own bit in mie. Two reasons. First, clearing a source is
// block-specific (write mtimecmp, write msip, write the timer's IP bit)
// and putting three peripherals' register maps in the trap path would
// make this file a driver. Second, masking is the generic thing that is
// always available and always correct: Ibex's interrupt inputs are
// LEVEL-sensitive and the core re-enters the handler immediately on
// mret if the line is still high, so a handler that neither cleared nor
// masked would be an infinite loop that presents as a simulation
// timeout. The C code clears the source and unmasks afterwards, which is
// also what makes the masking observable to the test.
//
// mepc is NOT advanced. For an interrupt mepc is the instruction that
// was about to run, not one that faulted; advancing it would silently
// skip an instruction of the interrupted program.
// ---------------------------------------------------------------------
irq_common:
  addi  sp, sp, -32
  sw    t1, 4(sp)
  sw    t2, 8(sp)
  sw    t3, 12(sp)

  la    t1, irq_marker
  sw    t0, 0(t1)

  csrr  t2, mcause
  la    t1, irq_mcause
  sw    t2, 0(t1)

  la    t1, irq_count
  lw    t3, 0(t1)
  addi  t3, t3, 1
  sw    t3, 0(t1)

  // Mask this source: mie &= ~(1 << mcause[4:0]). The NMI has no mie bit
  // and does not come here.
  andi  t2, t2, 31
  li    t3, 1
  sll   t3, t3, t2
  csrc  mie, t3

  lw    t1, 4(sp)
  lw    t2, 8(sp)
  lw    t3, 12(sp)
  addi  sp, sp, 32
  mret

// ---------------------------------------------------------------------
// Non-maskable interrupt: watchdog stage 1.
//
// This one MUST clear its source rather than mask it, because there is
// nothing to mask -- irq_nm_i is not in mie and not in mip, by design
// (hw/soc/rtl/soc_wdog.v W3). If this handler returned without
// acknowledging, mret would leave NMI mode with the line still high and
// the core would re-enter immediately, forever, until the watchdog's
// stage 2 reset ended it. Which is, to be fair, the correct outcome --
// but it is not a handler.
//
// It acknowledges and does NOT kick. Proving the software is alive is a
// different statement from noticing that the watchdog complained, and a
// stage-1 handler that kicked would let a program that does nothing else
// keep the watchdog satisfied forever from inside its own failure.
// ---------------------------------------------------------------------
#ifdef SOC_PLATFORM
vec_nmi:
  addi  sp, sp, -32
  sw    t0, 0(sp)
  sw    t1, 4(sp)
  sw    t2, 8(sp)

  li    t0, 31
  la    t1, irq_marker
  sw    t0, 0(t1)

  csrr  t0, mcause
  la    t1, irq_mcause
  sw    t0, 0(t1)

  la    t1, nmi_count
  lw    t2, 0(t1)
  addi  t2, t2, 1
  sw    t2, 0(t1)

  // WDOGSTAT write-one-to-clear on the NMI bit, with the key -- unless
  // nmi_no_ack says not to.
  //
  // That flag exists for one purpose: hw/soc/flow/sim_soc.sh's watchdog
  // demonstration needs software that SEES the stage-1 warning and does
  // nothing about it, because that is the case stages 2 and 3 exist for
  // and there is no other way to reach them from inside a program that
  // works. It is zero in every normal build and the whole ladder is
  // therefore unreachable in one.
  la    t1, nmi_no_ack
  lw    t2, 0(t1)
  bnez  t2, 1f
  li    t0, WDOG_STAT
  li    t1, WDOG_W(WDOG_ST_NMI)
  sw    t1, 0(t0)
1:

  lw    t0, 0(sp)
  lw    t1, 4(sp)
  lw    t2, 8(sp)
  addi  sp, sp, 32
  mret
#else
  // No watchdog on the minimal platform of docs/38. The entry still
  // exists so the table is 32 entries wide and every offset is right.
vec_nmi:
  li    t0, 31
  j     irq_common
#endif

// ---------------------------------------------------------------------
// Synchronous exception handler. Entered at vector 0 for every cause.
// ---------------------------------------------------------------------
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
  .global irq_marker
  .global irq_mcause
  .global irq_count
  .global nmi_count
  .global nmi_no_ack
trap_mcause:   .word 0
trap_mepc:     .word 0
trap_count:    .word 0
trap_saw_rvc:  .word 0
irq_marker:    .word 0
irq_mcause:    .word 0
irq_count:     .word 0
nmi_count:     .word 0
nmi_no_ack:    .word 0
#ifdef SOC_PLATFORM
  .global exit_code
  .global exit_magic
exit_code:     .word 0
exit_magic:    .word 0
#endif
