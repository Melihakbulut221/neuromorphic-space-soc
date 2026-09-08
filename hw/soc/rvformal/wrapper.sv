// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// riscv-formal binding for this project's Ibex configuration.
//
// docs/63 is the record of what this proves and what it does not. Read
// section 4 of that document before believing anything about this file:
// EVERY `assume` below narrows the set of traces the solver considers,
// and a proof is only as strong as the assumptions under it.
//
// WHAT THIS IS. riscv-formal (https://github.com/YosysHQ/riscv-formal,
// pinned by commit in hw/soc/tools.soc.mk) is a formal description of
// the RISC-V ISA plus a set of checks that bind to any core exposing an
// RVFI retirement trace. This module is the binding: it instantiates
// `ibex_top` at the parameters hw/soc/rtl/soc_top.v instantiates it
// with, drives its two memory ports from free (solver-chosen) inputs
// under the protocol assumptions in section 3 below, and exports the
// RVFI trace to riscv-formal's testbench.
//
// THE CORE READ HERE IS hw/soc/genrvfi/, NOT hw/soc/gen/. The two are
// the same sv2v conversion of the same pinned Ibex commit; genrvfi adds
// `--define=RVFI`, which turns on the trace-port block at
// ibex_top.sv line 138. `hw/soc/gen/` -- the RTL the SoC is built and
// measured from -- has no RVFI ports at all (`grep -c rvfi
// hw/soc/gen/ibex_top.v` returns 0), so binding to it is not possible
// and generating a second tree is not optional.
//
// THE REGISTER FILE IS UPSTREAM'S. This is phase 1 of docs/63 and it
// deliberately does NOT substitute hw/soc/rtl/ibex_regfile_secded.v
// (docs/43 section 6). The point of running the stock core first is
// that a phase-2 failure then has a baseline to be a delta against;
// without one, a failure cannot be attributed to the harness or to the
// substitution. hw/soc/flow/rvformal.sh selects between them and
// defaults to upstream.

module rvfi_wrapper (
	input         clock,
	input         reset,
	`RVFI_OUTPUTS
);

	// ------------------------------------------------------------------
	// 1. Free inputs
	//
	// `rvformal_rand_reg is `rand reg` under Yosys: a fresh solver-chosen
	// value every cycle. These are the two memory ports and the interrupt
	// lines -- everything the core does not control.
	// ------------------------------------------------------------------
	(* keep *) `rvformal_rand_reg        instr_gnt;
	(* keep *) `rvformal_rand_reg        instr_rvalid;
	(* keep *) `rvformal_rand_reg [31:0] instr_rdata;

	(* keep *) `rvformal_rand_reg        data_gnt;
	(* keep *) `rvformal_rand_reg        data_rvalid;
	(* keep *) `rvformal_rand_reg [31:0] data_rdata;

	// The boot address is a free CONSTANT, not a free signal: it is a
	// pin, it does not change while the core runs, and leaving it free
	// means the proofs hold for every board that ties it anywhere legal
	// rather than only for this SoC's 0x0000_0000. Ibex forms its reset
	// vector as {boot_addr_i[31:8], 8'h80} and its exception vector as
	// {mtvec[31:8], 8'h00}, so the low eight bits are ignored either way.
	(* keep *) `rvformal_rand_const_reg [31:0] boot_addr;

	// ------------------------------------------------------------------
	// 2. Interrupts and debug
	//
	// The interrupt lines are FREE. riscv-formal's PC checks relax
	// themselves on `rvfi_intr`, so an asynchronous trap entry does not
	// have to be assumed away, and leaving them free is a stronger
	// statement than tying them off. What this does NOT do is check that
	// the trap was taken CORRECTLY -- riscv-formal has no model of
	// mtvec/mepc/mcause, and Ibex exposes no rvfi_csr_* ports for one to
	// bind to. docs/63 section 6 states that gap at length.
	//
	// debug_req_i is tied LOW. Ibex's own dv/formal flow excludes
	// debug-mode entry for the same reason: entering debug mode diverts
	// the PC to a debug ROM address that no ISA model describes, so the
	// PC checks would report a violation of a rule that does not apply.
	// This is a DELIBERATE DISABLE, ledgered as A8 in docs/63 section
	// 4.1.
	// ------------------------------------------------------------------
	(* keep *) `rvformal_rand_reg        irq_software;
	(* keep *) `rvformal_rand_reg        irq_timer;
	(* keep *) `rvformal_rand_reg        irq_external;
	(* keep *) `rvformal_rand_reg [14:0] irq_fast;
	(* keep *) `rvformal_rand_reg        irq_nm;

	// ------------------------------------------------------------------
	// 3. Bus protocol assumptions
	//
	// These are not conveniences. Ibex's memory interface is a req/gnt
	// protocol with a decoupled response phase, and a response the core
	// never asked for is not a bus this design can be built on -- it is
	// an environment that violates the interface contract. Left
	// unconstrained the solver produces exactly that in the first
	// counterexample, and the counterexample says nothing about the core.
	//
	//   A1  a grant only in a cycle the core is requesting
	//   A2  a response only against a grant given in an EARLIER cycle
	//
	// Both are stated over counters built here rather than over anything
	// inside the core, so nothing in the core is assumed about itself.
	//
	// A2 IS THE SECOND HARNESS DEFECT THIS EXERCISE FOUND, and the
	// first version of it read `instr_out_next != 0` -- which permits a
	// response in the SAME cycle as the grant. Ibex's memory interface
	// does not:
	//
	//     "The memory answers with a data_rvalid_i set high for exactly
	//      one cycle ... This may happen one or more cycles AFTER the
	//      grant has been received."
	//     (doc/03_reference/load_store_unit.rst step 3, at the pinned
	//      commit) [fact]
	//
	// With the weaker version the `hang` check failed at depth 25 on a
	// trace whose store was granted and answered in one cycle: the LSU
	// completed it immediately, the ID stage had already moved to its
	// multi-cycle state expecting a later response, and the core stalled
	// for ever. That is a deadlock, it is real, and it is reachable only
	// on a bus the core is not specified to work with -- so it is an
	// environment defect and not a core defect, and the counter is now
	// read one cycle late.
	//
	// OUTSTANDING BOUNDS. The instruction port allows TWO outstanding
	// requests (Ibex's prefetch buffer, NUM_REQS = 2). The data port
	// allows TWO as well, and that is the FIRST harness defect this
	// exercise found: P2 was written as `<= 1` from the one-request-at-a-
	// time reading of the LSU, and `unique_ch0` produced a counterexample
	// in three minutes -- a MISALIGNED word access, which the LSU splits
	// into two bus requests and for which it takes the second grant
	// before the first response arrives (`data_be` 4'hE at 0x104 then
	// 4'h1 at 0x108, two grants, no response). The bound is a fact about
	// the core and it is 2, not 1. Anything placing this core on a bus
	// needs to know that.
	//
	// The counters are three bits so that a violation of the core's own
	// bound is visible as a count rather than a silent wrap, and P1/P2
	// ASSERT the bound rather than assuming it -- which makes the core's
	// half of the contract a proved obligation instead of a matching
	// assumption that could hide the very thing it describes.
	// ------------------------------------------------------------------
	(* keep *) wire        instr_req;
	(* keep *) wire [31:0] instr_addr;
	(* keep *) wire        data_req;
	(* keep *) wire        data_we;
	(* keep *) wire [3:0]  data_be;
	(* keep *) wire [31:0] data_addr;
	(* keep *) wire [31:0] data_wdata;

	reg [2:0] instr_out = 0;
	reg [2:0] data_out  = 0;

	wire [2:0] instr_out_next = instr_out + (instr_req && instr_gnt);
	wire [2:0] data_out_next  = data_out  + (data_req  && data_gnt );

	always @* begin
		// A1
		assume (!instr_gnt || instr_req);
		assume (!data_gnt  || data_req );
		// A2 -- `instr_out`, not `instr_out_next`: the grant must be in
		// an earlier cycle than the response.
		assume (!instr_rvalid || instr_out != 0);
		assume (!data_rvalid  || data_out  != 0);
	end

	always @(posedge clock) begin
		if (reset) begin
			instr_out <= 0;
			data_out  <= 0;
		end else begin
			instr_out <= instr_out_next - instr_rvalid;
			data_out  <= data_out_next  - data_rvalid;
			// P1/P2. The core's side of the same contract, ASSERTED.
			assert (instr_out_next <= 2);
			assert (data_out_next  <= 2);
		end
	end

`ifdef IBEX_FAIRNESS
	// Bounded response, for the liveness and hang checks only. Without
	// it a solver satisfies "the core never retires an instruction" by
	// never answering a fetch, which is a statement about the memory and
	// not about the core.
	//
	// TWO cycles for the grant and FOUR for the response. Ibex's own
	// dv/formal flow bounds the same thing at ten; this is tighter, and
	// tighter is a STRONGER assumption, so the reason is recorded rather
	// than the number alone. `hang` is a bounded check -- it asks
	// whether an instruction retires by cycle 30 -- and the two bounds
	// and the depth have to be consistent with each other or the check
	// fails for arithmetic rather than for anything about the core.
	// With an eight-cycle response bound the FIRST version of this
	// failed at depth 25 on a trace that was doing nothing wrong: a
	// misaligned store, which needs two bus responses, could not get
	// both of them inside the window. Raising the depth instead would
	// have cost solver time on every one of the two checks that need
	// this; tightening the environment costs an assumption, and the
	// assumption is that memory answers within four cycles, which this
	// SoC's does (hw/soc/rtl/soc_mem.v).
	//
	// The registers are shift registers, so what is bounded is the
	// CONSECUTIVE wait: a memory that answers one request every four
	// cycles for ever satisfies this, and that is the intended meaning.
	reg [1:0] instr_gnt_wait = 0;
	reg [1:0] data_gnt_wait  = 0;
	reg [3:0] instr_rsp_wait = 0;
	reg [3:0] data_rsp_wait  = 0;

	always @(posedge clock) begin
		instr_gnt_wait <= reset ? 0 : {instr_gnt_wait, instr_req && !instr_gnt};
		data_gnt_wait  <= reset ? 0 : {data_gnt_wait,  data_req  && !data_gnt };
		instr_rsp_wait <= reset ? 0 : {instr_rsp_wait, instr_out != 0 && !instr_rvalid};
		data_rsp_wait  <= reset ? 0 : {data_rsp_wait,  data_out  != 0 && !data_rvalid };
		assume (~&instr_gnt_wait);
		assume (~&data_gnt_wait );
		assume (~&instr_rsp_wait);
		assume (~&data_rsp_wait );
	end
`endif

	// ------------------------------------------------------------------
	// 4. Bus errors are assumed absent
	//
	// instr_err_i and data_err_i are tied LOW rather than left free.
	//
	// Ibex responds to a bus error by taking a load/store or instruction
	// access fault, so a retired instruction reports rvfi_trap = 1 for a
	// reason that is outside the instruction's own semantics.
	// riscv-formal can express that -- `RISCV_FORMAL_MEM_FAULT` and the
	// rvfi_mem_fault* signals exist for it -- but Ibex's RVFI has no
	// such port, so the checker would compare a trap it can see against
	// a spec that cannot produce one and report a failure that is a
	// modelling gap and not a defect. Ibex's own dv/formal states the
	// same exclusion ("bus errors assumed absent").
	//
	// The consequence is exact, it is ledgered as A3 in docs/63 section
	// 4.1, and section 6 restates it: nothing here
	// says anything about the core's behaviour on a bus error, and
	// hw/soc/rtl/soc_bus.v raises one on every unmapped address.
	// ------------------------------------------------------------------

	// ------------------------------------------------------------------
	// 5. PMP and privilege
	//
	// Both of these narrow the traces and both are switched on from
	// checks.cfg so that they appear in the generated .sby files rather
	// than only here.
	//
	// IBEX_ASSUME_MMODE. riscv-formal's instruction models are
	// privilege-blind: they assert `spec_trap == rvfi_trap`, and a PMP
	// denial is a trap the model cannot produce. With every pmpcfg at
	// its reset value of zero, U-mode denies EVERY access (RISC-V
	// privileged spec: no matching entry outside M-mode fails), so
	// without this the solver's shortest counterexample to every
	// load and store check is "enter U-mode, then execute it".
	//
	// IBEX_ASSUME_NO_PROT_CSR_WRITE. In M-mode with every pmpcfg at its
	// reset value the PMP is transparent, so nothing is needed -- until
	// a CSR write makes it bite. FOUR registers do that and the first
	// version of this assumption named only two of them:
	//
	//   pmpcfg0-15   (0x3A0-0x3AF)  a locked entry denies in M-mode
	//   pmpaddr0-63  (0x3B0-0x3EF)  the addresses those entries match
	//   mseccfg      (0x747)        MML or MMWP makes a NO-MATCH deny
	//                               in M-mode, which with the reset
	//                               configuration denies EVERYTHING
	//   mseccfgh     (0x757)
	//   mstatus      (0x300)        MPRV redirects load/store privilege
	//                               to MPP, so a U-mode LSU access is
	//                               reachable without ever leaving
	//                               M-mode -- and with no matching
	//                               entry, U-mode is denied
	//
	// The mseccfg one is recorded here because it was FOUND rather than
	// foreseen: the very first check run, `insn_add_ch0`, failed at
	// depth 20 with a trace whose only interesting feature was
	// `csr_pmp_mseccfg = 3'b001`, MML set, every fetch denied, every
	// instruction retiring with rvfi_trap. That is the harness being
	// wrong and the tool saying so, which is the argument for running it.
	//
	// AN INCOMPLETE ASSUMPTION SET HERE IS LOUD, NOT SILENT, and that is
	// worth stating because it is what makes this shape of assumption
	// safe to iterate on. Too WEAK and a check fails with a
	// counterexample naming the register, as above. Too STRONG and the
	// check becomes vacuous -- and the cover run of checks.cfg.in
	// catches that, because it fails when the instruction can no longer
	// retire at the check cycle. Both directions have an alarm.
	//
	// WHAT IT COSTS, stated so it is not read as a technicality: the PMP
	// hardware is present, elaborated, and in the load/store path of
	// everything proved here, but NOTHING BELOW PROVES PMP ENFORCEMENT.
	// The evidence for that is still docs/38 section 7.2 test 10, a
	// single simulated case. docs/63 section 4.1 ledgers these two as A4
	// and A5 and section 6 gives them their own paragraph, because of
	// everything not covered here this is the largest.
	// ------------------------------------------------------------------
	wire [11:0] rvfi_csr_addr  = rvfi_insn[31:20];
	wire [ 2:0] rvfi_csr_f3    = rvfi_insn[14:12];
	// funct3 == 000 is ecall/ebreak/mret/wfi, which is not a CSR access.
	wire        rvfi_is_csr_op = (rvfi_insn[6:0] == 7'b1110011) &&
	                             (rvfi_csr_f3 != 3'b000);
	// csrrw/csrrwi (funct3 001/101) always write. csrrs/csrrc and their
	// immediate forms write only when the source operand is non-zero,
	// and rvfi_insn[19:15] carries both the register number and the
	// 5-bit immediate. Being this precise costs four lines and keeps
	// the assumption from also forbidding a READ of these registers.
	wire        rvfi_csr_write = rvfi_is_csr_op &&
	                             ((rvfi_csr_f3[1:0] == 2'b01) ||
	                              (rvfi_insn[19:15] != 5'b0));
	wire        rvfi_csr_prot  = (rvfi_csr_addr == 12'h300) ||
	                             (rvfi_csr_addr == 12'h747) ||
	                             (rvfi_csr_addr == 12'h757) ||
	                             ((rvfi_csr_addr >= 12'h3A0) &&
	                              (rvfi_csr_addr <= 12'h3EF));

	always @* begin
`ifdef IBEX_ASSUME_MMODE
		if (rvfi_valid) assume (rvfi_mode == 2'b11);
`endif
`ifdef IBEX_ASSUME_NO_PROT_CSR_WRITE
		if (rvfi_valid && rvfi_csr_write) assume (!rvfi_csr_prot);
`endif
	end

	// ------------------------------------------------------------------
	// 5a. rvfi_intr: Ibex's meaning is NARROWER than riscv-formal's, and
	//     this is the adapter
	//
	// riscv-formal's PC checks relax themselves when `rvfi_intr` is set,
	// because the address a trap handler starts at is not a function of
	// the instruction before it and no ISA model here describes it. The
	// RVFI convention is that rvfi_intr marks "the first instruction of
	// a TRAP HANDLER" -- any trap handler.
	//
	// Ibex sets it only for ASYNCHRONOUS interrupts. `ibex_core.sv`:
	//
	//     if (pc_set && pc_mux_id == PC_EXC && (exc_pc_mux_id == EXC_PC_IRQ))
	//       rvfi_set_trap_pc_d = 1'b1;
	//
	// EXC_PC_IRQ and not EXC_PC_EXC, so an illegal instruction, an
	// ecall, an ebreak or an access fault vectors to the handler with
	// rvfi_intr LOW on the handler's first instruction [fact, the RTL at
	// the pinned commit].
	//
	// FOUND, NOT FORESEEN. `pc_fwd_ch0` failed at depth 30 on exactly
	// that: `c.lwsp` with rd = x0, which is reserved, retiring with
	// rvfi_trap = 1 and pc_wdata = pc + 2, and the next instruction
	// starting at 0x1000 -- the mtvec Ibex derives from boot_addr --
	// with rvfi_intr = 0. The PC check had no reason to look away and
	// reported the discontinuity.
	//
	// The adapter ORs in "the previous retired instruction trapped".
	//
	// WHAT IT HIDES, which has to be said because an adapter is exactly
	// where a real defect can be smoothed over: it makes the PC checks
	// blind to the handler entry address after a synchronous exception.
	// That costs nothing that was ever checked -- riscv-formal has no
	// mtvec, mepc or mcause model, Ibex exposes no rvfi_csr_* ports to
	// bind one to, and the asynchronous case was already relaxed by
	// Ibex's own rvfi_intr. What it does NOT hide is the trapping
	// instruction itself: `assert(spec_trap == trap)` in every
	// instruction check still runs, unrelaxed, on the instruction that
	// caused the trap. docs/63 section 4.1 A9 and section 7.4.
	// ------------------------------------------------------------------
	// AND THE SAME IS TRUE OF `mret`, which the first version of this
	// adapter did not cover and which `pc_fwd_ch0` then failed on at
	// depth 30 with the adapter already in place. `ibex_core.sv` builds
	// the reported next PC as
	//
	//     rvfi_stage_pc_wdata[i] <= pc_set ? branch_target_ex : pc_if;
	//
	// and `branch_target_ex` is the ALU's target, which is the right
	// answer for PC_JUMP and PC_BP and is NOT the right answer for
	// PC_ERET, whose target is `csr_mepc`. In the counterexample an
	// `mret` at PC 0 reported `rvfi_pc_wdata = 4` and the next
	// instruction started at 0x80, which is where mepc pointed [fact].
	//
	// SO THIS IS A REAL DEVIATION FROM THE RVFI DEFINITION AND NOT A
	// HARNESS PROBLEM: rvfi_pc_wdata is specified as the address of the
	// next instruction, and for a PC redirect that is not a branch or a
	// jump, Ibex's is not. It is recorded as a finding in docs/63
	// section 7.4 rather than only worked around here. The workaround is
	// the same relaxation as for a trap, and it conceals the same thing
	// and nothing more: the entry address of a handler or a return,
	// which riscv-formal cannot check anyway for want of an mepc model.
	(* keep *) wire rvfi_intr_core;
	reg  prev_redirect = 0;

	wire rvfi_is_mret = (rvfi_insn == 32'h30200073);

	always @(posedge clock) begin
		if (reset)           prev_redirect <= 0;
		else if (rvfi_valid) prev_redirect <= rvfi_trap | rvfi_is_mret;
	end

	assign rvfi_intr = rvfi_intr_core | prev_redirect;

	// ------------------------------------------------------------------
	// 6. The core
	//
	// NO PARAMETER OVERRIDES HERE, and their absence is the thing worth
	// reading. The core is elaborated by yosys-slang rather than by
	// Yosys's own Verilog front end -- docs/63 section 3 gives the
	// reason, which is that Ibex's RVFI block reaches into submodules by
	// hierarchical reference and the Verilog-2005 front end cannot
	// resolve those. read_slang elaborates `ibex_top` completely, so the
	// module it leaves in RTLIL is NOT parametric and an override here
	// is a hard error rather than an override:
	//
	//     ERROR: Module `ibex_top' is used with parameters but is not
	//            parametric!
	//
	// The nineteen parameters are therefore passed to read_slang with
	// -G, from hw/soc/rvformal/checks.cfg.in, and
	// hw/soc/rvformal/params.sh reads them back out of THAT file and out
	// of hw/soc/rtl/soc_top.v and fails if any of them has moved.
	// ------------------------------------------------------------------
	ibex_top uut (
		.clk_i  (clock),
		.rst_ni (!reset),

		.test_en_i             (1'b0),
		.scan_rst_ni           (1'b1),

		.ram_cfg_icache_tag_i  (24'h0),
		.ram_cfg_icache_tag_o  (),
		.ram_cfg_icache_data_i (24'h0),
		.ram_cfg_icache_data_o (),

		// ibex_pkg::IbexMuBiOff -- the CHERIoT half of this dual-ISA
		// core is held off, as in soc_top.v.
		.cheriot_enable_i (4'b1010),

		.hart_id_i             (32'h0),
		.boot_addr_i           (boot_addr),
		.trvk_heap_base_addr_i (32'h0),

		.instr_req_o        (instr_req),
		.instr_gnt_i        (instr_gnt),
		.instr_rvalid_i     (instr_rvalid),
		.instr_addr_o       (instr_addr),
		.instr_rdata_i      (instr_rdata),
		.instr_rdata_intg_i (7'h0),      // MemECC = SecureIbex = 0
		.instr_err_i        (1'b0),      // section 4

		.data_req_o        (data_req),
		.data_gnt_i        (data_gnt),
		.data_rvalid_i     (data_rvalid),
		.data_we_o         (data_we),
		.data_be_o         (data_be),
		.data_addr_o       (data_addr),
		.data_wdata_o      (data_wdata),
		.data_wdata_intg_o (),
		.data_tag_o        (),
		.data_rdata_i      (data_rdata),
		.data_rdata_intg_i (7'h0),
		.data_tag_i        (1'b0),
		.data_err_i        (1'b0),       // section 4

		.trvk_revbm_req_o        (),
		.trvk_revbm_gnt_i        (1'b0),
		.trvk_revbm_rvalid_i     (1'b0),
		.trvk_revbm_addr_o       (),
		.trvk_revbm_rdata_i      (32'h0),
		.trvk_revbm_rdata_intg_i (7'h0),
		.trvk_revbm_err_i        (1'b0),

		.irq_software_i (irq_software),
		.irq_timer_i    (irq_timer),
		.irq_external_i (irq_external),
		.irq_fast_i     (irq_fast),
		.irq_nm_i       (irq_nm),

		.scramble_key_valid_i (1'b0),
		.scramble_key_i       (128'h0),
		.scramble_nonce_i     (64'h0),
		.scramble_req_o       (),

		.debug_req_i         (1'b0),     // section 2
		.crash_dump_o        (),
		.double_fault_seen_o (),

		.fetch_enable_i        (4'b0101), // ibex_pkg::IbexMuBiOn
		.mcounteren_writable_i (4'b1010), // ibex_pkg::IbexMuBiOff

		.alert_minor_o          (),
		.alert_major_internal_o (),
		.alert_major_bus_o      (),
		.core_sleep_o           (),

		.lockstep_cmp_en_o        (),
		.data_req_shadow_o        (),
		.data_we_shadow_o         (),
		.data_be_shadow_o         (),
		.data_addr_shadow_o       (),
		.data_wdata_shadow_o      (),
		.data_wdata_intg_shadow_o (),
		.instr_req_shadow_o       (),
		.instr_addr_shadow_o      (),

		// ---- the RVFI trace ----
		//
		// Connected by name and one at a time rather than through
		// riscv-formal's `RVFI_CONN macro, because Ibex's port set is
		// NOT riscv-formal's: it carries three CHERIoT capability
		// ports, an rs3 channel, and fifteen rvfi_ext_* signals that
		// riscv-formal has no name for, and it does NOT carry the
		// rvfi_csr_* ports riscv-formal's CSR checks bind to. A macro
		// that matched by position would connect the wrong wires; a
		// macro that matched by name would fail to elaborate. The
		// mismatch is the subject of docs/63 section 6.
		.rvfi_valid     (rvfi_valid),
		.rvfi_order     (rvfi_order),
		.rvfi_insn      (rvfi_insn),
		.rvfi_trap      (rvfi_trap),
		.rvfi_halt      (rvfi_halt),
		.rvfi_intr      (rvfi_intr_core),
		.rvfi_mode      (rvfi_mode),
		.rvfi_ixl       (rvfi_ixl),
		.rvfi_rs1_addr  (rvfi_rs1_addr),
		.rvfi_rs2_addr  (rvfi_rs2_addr),
		.rvfi_rs1_rdata (rvfi_rs1_rdata),
		.rvfi_rs2_rdata (rvfi_rs2_rdata),
		.rvfi_rd_addr   (rvfi_rd_addr),
		.rvfi_rd_wdata  (rvfi_rd_wdata),
		.rvfi_pc_rdata  (rvfi_pc_rdata),
		.rvfi_pc_wdata  (rvfi_pc_wdata),
		.rvfi_mem_addr  (rvfi_mem_addr),
		.rvfi_mem_rmask (rvfi_mem_rmask),
		.rvfi_mem_wmask (rvfi_mem_wmask),
		.rvfi_mem_rdata (rvfi_mem_rdata),
		.rvfi_mem_wdata (rvfi_mem_wdata),

		// Ibex ports riscv-formal has no binding for. Left open, and
		// listed rather than omitted so that the set of things this
		// harness does not look at is readable in one place.
		.rvfi_rs3_addr  (),
		.rvfi_rs3_rdata (),
		.rvfi_rs1_rcap  (),
		.rvfi_rs2_rcap  (),
		.rvfi_rd_wcap   (),
		.rvfi_mem_is_cap(),
		.rvfi_mem_rcap  (),
		.rvfi_mem_wcap  (),

		.rvfi_ext_pre_mip             (),
		.rvfi_ext_post_mip            (),
		.rvfi_ext_nmi                 (),
		.rvfi_ext_nmi_int             (),
		.rvfi_ext_debug_req           (),
		.rvfi_ext_debug_mode          (),
		.rvfi_ext_rf_wr_suppress      (),
		.rvfi_ext_mcycle              (),
		.rvfi_ext_mhpmcounters        (),
		.rvfi_ext_mhpmcountersh       (),
		.rvfi_ext_ic_scr_key_valid    (),
		.rvfi_ext_irq_valid           (),
		.rvfi_ext_expanded_insn_valid (),
		.rvfi_ext_expanded_insn       (),
		.rvfi_ext_expanded_insn_last  ()
	);
endmodule
