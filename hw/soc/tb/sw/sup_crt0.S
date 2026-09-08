// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: Apache-2.0

// Startup, vector table and privilege-switch primitives for the static
// partitioned supervisor of hw/soc/tb/sw/fi_supervisor.c.
//
// WHY THIS IS A SECOND STARTUP FILE, WHICH IS A COST
//
// hw/soc/tb/sw/crt0.S is the startup of docs/38 to docs/43. It is shared
// by the bring-up program and by fi_workload.c precisely so that the
// reset sequence, the mtvec constraint and the trap handler cannot
// drift, and duplicating it is a real cost that is recorded here rather
// than discovered later.
//
// It is duplicated anyway, for one reason that cannot be worked around
// and one that could be but should not be:
//
//   * crt0.S's synchronous-exception handler advances mepc past the
//     faulting instruction and returns. A supervisor whose partitions
//     run in U-mode and return by `ecall` needs that trap to switch
//     privilege and stack instead, which is not a variation on crt0.S's
//     handler, it is a different handler.
//   * the alternative -- a hook in crt0.S -- would change the
//     instruction stream of the bring-up program and of fi_workload.c.
//     docs/43 section 9.1 rests on both of those being cycle-identical
//     to docs/40 and docs/41, and on fi_workload.c's ROM image being
//     byte-identical to docs/42's. Buying a shared file with the loss of
//     that regression would be a bad trade.
//
// WHAT STOPS THE COPY DRIFTING ON THE THINGS THAT MATTER
//
// The two Ibex constraints that cost docs/38 a debugging session each
// are enforced by the LINKER SCRIPT, which is shared and is not copied:
// hw/soc/tb/sw/link_soc.ld asserts `_start == __soc_reset_vector`
// (docs/38 section 7.5 defect 4), `trap_vectors` 256-byte aligned
// (defect 3 -- Ibex forces mtvec[7:2] to zero and has no direct mode)
// and the vector table exactly 128 bytes. This file cannot get any of
// the three wrong without the link failing.
//
// WHAT IS HERE
//
//   _start            reset entry: mtvec, sp, gp, .bss, .data, main
//   trap_vectors      32 entries of 4 bytes, Ibex's vectored mtvec
//   sup_exception     vector 0: every synchronous exception
//   sup_tick          vector 7: the machine timer, the frame tick
//   sup_nmi           vector 31: watchdog stage 1
//   sup_dispatch      M-mode -> U-mode, returning when the partition
//                     executes `ecall`
//
// THE PRIVILEGE SWITCH, IN ONE PARAGRAPH
//
// `sup_dispatch` saves the supervisor's callee-saved registers and its
// stack pointer, points mepc at the partition's entry, sets mstatus.MPP
// to U and mret's. The partition runs on its own stack, inside its own
// PMP region, and ends by executing `ecall`. `sup_exception` sees
// mcause = 8, restores the supervisor's stack pointer, points mepc at
// the instruction after the dispatch and mret's back into M-mode. The
// partition's register state is not saved anywhere, because it is not
// resumed: this is a run-to-completion static architecture in the
// Microkit style that docs/09 part B track 3 chose, not a preemptive
// thread scheduler.
//
// A partition that faults instead of returning is TERMINATED and the
// supervisor carries on with the next one -- which is what a partitioned
// supervisor does, and which is why `sup_exception` returns to the
// supervisor from a U-mode fault rather than trying to resume the
// partition.

#include "soc_timers.h"
#include "sup_config.h"

  .section .text.start, "ax"
  .global _start
  .option norvc
_start:
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

  // Relocate .data from the boot ROM to RAM. crt0.S's comment applies
  // unchanged: the copy reads through the ROM slave and writes through
  // the RAM slave, so a decode that sent one of them to the wrong place
  // would corrupt every initialised variable before main is entered.
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

  call  main

  // Terminate by sleeping, with the exit code in a known word and the
  // magic beside it saying the word is meaningful. tb_soc_fi.v watches
  // core_sleep_o and then reads both.
  la    t0, exit_code
  sw    a0, 0(t0)
  la    t0, exit_magic
  li    t1, 0x600dc0de
  sw    t1, 0(t0)
  fence
3:
  wfi
  j     3b

  .option rvc

// =====================================================================
// The vector table.
//
// Thirty-two entries of exactly four bytes at offsets 0x00..0x7C, which
// is what Ibex's exception-PC arithmetic demands: synchronous exceptions
// enter at BASE itself and interrupts at BASE + 4*cause. `.option norvc`
// over the whole table is load-bearing -- one entry assembled compressed
// would be two bytes and every later vector would be at the wrong
// offset. link_soc.ld asserts the table is 128 bytes, so that failure is
// a link error.
// =====================================================================
  .section .trapvec, "ax"
  .balign 256

  .option push
  .option norvc
  .global trap_vectors
trap_vectors:
  j     sup_exception     //  0  every synchronous exception
  j     sup_spurious      //  1
  j     sup_spurious      //  2
  j     sup_spurious      //  3  machine software: unused here
  j     sup_spurious      //  4
  j     sup_spurious      //  5
  j     sup_spurious      //  6
  j     sup_tick          //  7  machine timer: the frame tick
  j     sup_spurious      //  8
  j     sup_spurious      //  9
  j     sup_spurious      // 10
  j     sup_spurious      // 11  machine external: no PLIC, tied low
  j     sup_spurious      // 12
  j     sup_spurious      // 13
  j     sup_spurious      // 14
  j     sup_spurious      // 15
  j     sup_spurious      // 16  fast 0, UART0: polled, never enabled
  j     sup_spurious      // 17
  j     sup_spurious      // 18
  j     sup_spurious      // 19  fast 3, GPTIMER0
  j     sup_spurious      // 20
  j     sup_spurious      // 21
  j     sup_spurious      // 22
  j     sup_spurious      // 23
  j     sup_spurious      // 24
  j     sup_spurious      // 25
  j     sup_spurious      // 26
  j     sup_spurious      // 27
  j     sup_spurious      // 28
  j     sup_spurious      // 29
  j     sup_spurious      // 30
  j     sup_nmi           // 31  non-maskable: watchdog stage 1
  .global trap_vectors_end
trap_vectors_end:
  .option pop

// ---------------------------------------------------------------------
// An interrupt this SoC has no source for, taken anyway.
//
// It is recorded and MASKED -- masked and not cleared, because clearing
// is block-specific and there is by definition no block. mie's bit for
// the cause is the generic thing that is always available. The count is
// a self-check the C code reads: the golden run takes none.
// ---------------------------------------------------------------------
sup_spurious:
  addi  sp, sp, -16
  sw    t0, 0(sp)
  sw    t1, 4(sp)
  sw    t2, 8(sp)

  la    t1, sup_spurious_irqs
  lw    t2, 0(t1)
  addi  t2, t2, 1
  sw    t2, 0(t1)

  csrr  t0, mcause
  andi  t0, t0, 31
  li    t2, 1
  sll   t2, t2, t0
  csrc  mie, t2

  lw    t0, 0(sp)
  lw    t1, 4(sp)
  lw    t2, 8(sp)
  addi  sp, sp, 16
  mret

// ---------------------------------------------------------------------
// The frame tick: CLINT mtimecmp, vector 7.
//
// It does two things and deliberately not a third. It advances the
// deadline and it records that a frame boundary has passed. IT DOES NOT
// SCHEDULE AND IT DOES NOT KICK THE WATCHDOG -- see the "WHERE THE KICK
// GOES" section of fi_supervisor.c, which is where that decision is
// argued.
//
// The deadline is advanced ABSOLUTELY, mtimecmp += period, so the frame
// rate does not drift with interrupt latency, with a catch-up loop for
// the case where the previous frame overran its period. That is the
// textbook sequence and the catch-up is why an overrun costs a late
// frame rather than an interrupt storm.
//
// Only MTIMECMPL is written. MTIMECMPH is zeroed once at init and this
// program is far shorter than 2^32 clocks, so the 64-bit-register-on-a
// -32-bit-bus hazard soc_clint.v's header describes cannot arise here:
// the deadline only ever moves up, within the low word.
//
// It can be taken in U-mode, from inside a partition, or in M-mode, from
// the supervisor's idle wait. It pushes onto whichever stack is current.
// That is safe in both cases because the PMP regions this program
// installs are UNLOCKED, so they constrain U-mode only and M-mode
// retains full access -- the RISC-V privileged specification's own rule,
// and the reason test 10 of test_ibex.c has to set the L bit to make PMP
// apply to M-mode at all.
// ---------------------------------------------------------------------
sup_tick:
  addi  sp, sp, -16
  sw    t0, 0(sp)
  sw    t1, 4(sp)
  sw    t2, 8(sp)
  sw    t3, 12(sp)

  li    t0, CLINT_MTIMECMPL
  lw    t1, 0(t0)
  li    t3, SUP_TICK_PERIOD
  li    t2, CLINT_MTIMEL
  lw    t2, 0(t2)
1:
  add   t1, t1, t3
  bgeu  t2, t1, 1b            // still in the past: advance another period
  sw    t1, 0(t0)

  la    t0, sup_ticks
  lw    t1, 0(t0)
  addi  t1, t1, 1
  sw    t1, 0(t0)

  la    t0, sup_tick_pending
  li    t1, 1
  sw    t1, 0(t0)

  lw    t0, 0(sp)
  lw    t1, 4(sp)
  lw    t2, 8(sp)
  lw    t3, 12(sp)
  addi  sp, sp, 16
  mret

// ---------------------------------------------------------------------
// Non-maskable interrupt: watchdog stage 1, vector 31.
//
// crt0.S's handler, unchanged in substance and for its reasons. It MUST
// clear its source rather than mask it, because irq_nm_i is not in mie
// and not in mip by design (soc_wdog.v W3); a handler that returned
// without acknowledging would re-enter for ever until stage 2 ended it.
//
// It acknowledges and does NOT kick. Proving the software is alive and
// noticing that the watchdog complained are different statements, and a
// stage-1 handler that kicked would let a program that does nothing else
// keep the watchdog satisfied from inside its own failure.
// ---------------------------------------------------------------------
sup_nmi:
  addi  sp, sp, -16
  sw    t0, 0(sp)
  sw    t1, 4(sp)
  sw    t2, 8(sp)

  la    t1, nmi_count
  lw    t2, 0(t1)
  addi  t2, t2, 1
  sw    t2, 0(t1)

  li    t0, WDOG_STAT
  li    t1, WDOG_W(WDOG_ST_NMI)
  sw    t1, 0(t0)

  lw    t0, 0(sp)
  lw    t1, 4(sp)
  lw    t2, 8(sp)
  addi  sp, sp, 16
  mret

// ---------------------------------------------------------------------
// Every synchronous exception, vector 0.
//
// Three outcomes, in this order:
//
//   mcause == 8, an environment call from U-mode: the partition has
//     finished. Count it, restore the supervisor's stack and resume the
//     supervisor. THIS IS THE NORMAL PATH and it is deliberately not
//     counted in `trap_count`, so that `trap_count` keeps the meaning
//     docs/42 section 5 gives it -- an exception the golden run does not
//     take -- and stays at zero in a healthy run.
//
//   any other cause from U-mode: the partition faulted. Record the
//     cause, count it in `trap_count`, TERMINATE the partition and
//     resume the supervisor. A partitioned supervisor does not resume a
//     partition that violated its own memory region, and a handler that
//     tried would turn one PMP fault into a fault loop.
//
//   any cause from M-mode: the supervisor itself faulted. There is
//     nothing to terminate, so this takes crt0.S's route -- advance mepc
//     past the faulting instruction and return -- and relies on the
//     runaway guard below to end a run that cannot make progress.
//
// The runaway guard is crt0.S's, for crt0.S's reason: an unbounded trap
// loop shows up only as a simulation timeout, which says nothing about
// where it happened. Past 64 FAULTS the run is over with a distinct
// code. Environment calls are not faults and are not counted towards it,
// which is why a long schedule cannot trip it.
// ---------------------------------------------------------------------
sup_exception:
  addi  sp, sp, -16
  sw    t0, 0(sp)
  sw    t1, 4(sp)
  sw    t2, 8(sp)

  csrr  t0, mcause
  csrr  t1, mstatus
  srli  t1, t1, 11
  andi  t1, t1, 3               // mstatus.MPP: 0 = U, 3 = M

  li    t2, 8                   // ECALL from U-mode
  bne   t0, t2, sup_fault_path
  bnez  t1, sup_fault_path      // an M-mode ecall is not the normal path

  la    t1, sup_ecalls
  lw    t2, 0(t1)
  addi  t2, t2, 1
  sw    t2, 0(t1)
  j     sup_resume_supervisor

sup_fault_path:
  // Record the cause and where it happened, and count it.
  la    t2, trap_mcause
  sw    t0, 0(t2)
  csrr  t2, mepc
  la    t0, trap_mepc
  sw    t2, 0(t0)

  la    t0, trap_count
  lw    t2, 0(t0)
  addi  t2, t2, 1
  sw    t2, 0(t0)

  li    t0, 64
  bltu  t2, t0, sup_fault_continue
  la    t0, exit_code
  li    t2, 0xdead0001          // "trap storm"
  sw    t2, 0(t0)
  la    t0, exit_magic
  li    t2, 0x600dc0de
  sw    t2, 0(t0)
  fence
6:
  wfi
  j     6b

sup_fault_continue:
  bnez  t1, sup_fault_in_m

  // A U-mode fault: terminate the partition and tell the supervisor.
  csrr  t0, mcause
  la    t1, sup_fault
  sw    t0, 0(t1)
  j     sup_resume_supervisor

sup_fault_in_m:
  // The supervisor itself faulted. Advance mepc past the faulting
  // instruction, checking its width rather than assuming it: a
  // compressed instruction is two bytes and skipping four would resume
  // in the middle of the next one.
  csrr  t0, mepc
  lhu   t2, 0(t0)
  andi  t2, t2, 3
  li    t1, 3
  beq   t2, t1, 7f
  la    t1, trap_saw_rvc
  li    t2, 1
  sw    t2, 0(t1)
  addi  t0, t0, 2
  j     8f
7:
  addi  t0, t0, 4
8:
  csrw  mepc, t0

  lw    t0, 0(sp)
  lw    t1, 4(sp)
  lw    t2, 8(sp)
  addi  sp, sp, 16
  mret

// Return to the supervisor at the point sup_dispatch recorded, in
// M-mode, with interrupts on. The partition's register state is
// abandoned: it is not resumed, so there is nothing to restore.
sup_resume_supervisor:
  la    t0, sup_msp
  lw    sp, 0(t0)
  la    t0, sup_resume
  lw    t0, 0(t0)
  csrw  mepc, t0
  li    t0, 0x1800              // mstatus.MPP = M
  csrs  mstatus, t0
  li    t0, 0x80                // mstatus.MPIE = 1
  csrs  mstatus, t0
  mret

// ---------------------------------------------------------------------
// uint32_t sup_dispatch(void (*entry)(uint32_t *), void *stack_top,
//                       uint32_t *arg);
//
// Enter `entry` in U-mode with sp = stack_top and a0 = arg. Returns here
// when the partition executes `ecall` or faults.
//
// Every callee-saved register is saved, and gp with them: the partition
// runs arbitrary code and this function is a C function, so its caller
// is entitled to find s0..s11 and gp as it left them. ra is saved for
// the ordinary reason.
//
// The return value is not used by the supervisor -- it reads the
// partition's own memory and `sup_fault` instead -- and is left as
// whatever a0 holds, which is documented here so nobody reads it.
// ---------------------------------------------------------------------
  .section .text, "ax"
  .global sup_dispatch
  .type sup_dispatch, @function
sup_dispatch:
  addi  sp, sp, -64
  sw    ra,  0(sp)
  sw    gp,  4(sp)
  sw    s0,  8(sp)
  sw    s1,  12(sp)
  sw    s2,  16(sp)
  sw    s3,  20(sp)
  sw    s4,  24(sp)
  sw    s5,  28(sp)
  sw    s6,  32(sp)
  sw    s7,  36(sp)
  sw    s8,  40(sp)
  sw    s9,  44(sp)
  sw    s10, 48(sp)
  sw    s11, 52(sp)

  la    t0, sup_msp
  sw    sp, 0(t0)
  la    t0, sup_resume
  la    t1, sup_dispatch_ret
  sw    t1, 0(t0)

  // Interrupts OFF across the switch. mepc and mstatus.MPP are the
  // trap-return state, so a tick taken between writing them and the
  // mret would overwrite both and the mret would return to the tick's
  // own interruption point in M-mode instead of into the partition.
  // MPIE = 1 below puts interrupts back on the instant the mret lands.
  csrci mstatus, 8              // mstatus.MIE = 0
  csrw  mepc, a0
  li    t0, 0x1800              // mstatus.MPP = U
  csrc  mstatus, t0
  li    t0, 0x80                // mstatus.MPIE = 1: interrupts on in U
  csrs  mstatus, t0
  mv    sp, a1
  mv    a0, a2
  mret

  .global sup_dispatch_ret
sup_dispatch_ret:
  lw    ra,  0(sp)
  lw    gp,  4(sp)
  lw    s0,  8(sp)
  lw    s1,  12(sp)
  lw    s2,  16(sp)
  lw    s3,  20(sp)
  lw    s4,  24(sp)
  lw    s5,  28(sp)
  lw    s6,  32(sp)
  lw    s7,  36(sp)
  lw    s8,  40(sp)
  lw    s9,  44(sp)
  lw    s10, 48(sp)
  lw    s11, 52(sp)
  addi  sp, sp, 64
  ret
  .size sup_dispatch, . - sup_dispatch

// ---------------------------------------------------------------------
  .section .bss
  .align 4
  .global trap_mcause
  .global trap_mepc
  .global trap_count
  .global trap_saw_rvc
  .global nmi_count
  .global sup_ecalls
  .global sup_fault
  .global sup_ticks
  .global sup_tick_pending
  .global sup_spurious_irqs
  .global exit_code
  .global exit_magic
trap_mcause:       .word 0
trap_mepc:         .word 0
trap_count:        .word 0
trap_saw_rvc:      .word 0
nmi_count:         .word 0
sup_ecalls:        .word 0
sup_fault:         .word 0
sup_ticks:         .word 0
sup_tick_pending:  .word 0
sup_spurious_irqs: .word 0
sup_msp:           .word 0
sup_resume:        .word 0
exit_code:         .word 0
exit_magic:        .word 0
