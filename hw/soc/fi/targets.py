#!/usr/bin/env python3
"""The strata and the injection sites of the core fault-injection
campaign, written down ONCE.

WHY THIS FILE EXISTS RATHER THAN TWO LISTS

The campaign needs the same target list in two languages: Verilog, where
a hierarchical name has to be written literally because Icarus cannot be
handed one as a string, and Python, where the classifier has to know
which stratum a record belongs to.  Two copies of that list is one
copy too many.  If the Verilog thought site 17 was `mtvec` and the
Python thought it was `mcause`, every number in the campaign would be
attributed to the wrong structure and nothing would look wrong.

So this module is the list, `emit_vh()` generates the Verilog from it,
and the testbench dumps what it actually elaborated -- name, path and
`$bits` width per site -- which `campaign.py` compares against this
table before it injects anything.  A path that moved, a width that
changed and an index that slipped are all caught by that comparison
rather than by a reader.

THE STRATA, AND WHY THEY ARE THESE

`docs/16-fault-injection-campaign.md` section 6 ranks per structure
because an unstratified campaign spends its budget where the flip-flops
are.  In this core that is overwhelming: the architectural register file
is 992 of the 2,198 injectable RTL bits, so a uniform random campaign
would put nearly one injection in two into `x1`..`x31` and would give
the main control FSM -- fifteen bits -- an expected 0.7 injections in a
hundred.

The strata below are therefore drawn over the ARCHITECTURE -- the
structures the RISC-V privileged specification and the Ibex user manual
name -- and the campaign samples an equal number from each.  A stratum
is a thing one can make a decision about.  "The PMP configuration
registers" is a stratum because docs/09's software architecture rests on
them; "everything with `_q` in its name" is not.

WHAT IS DELIBERATELY NOT HERE

  * `ibex_top`'s scrambling key registers, the icache, the dummy
    instruction LFSR, the CHERIoT half, the lockstep wrapper and the
    debug trigger registers.  None of them exists at this
    configuration's parameters -- ICache 0, SecureIbex 0, DbgTriggerEn 0,
    BaseIsa RV32I -- so there is nothing to inject into.  The testbench
    dump is what proves that rather than this comment: a site that did
    not elaborate is a hard error there.
  * The writeback stage.  `WritebackStage = 0` selects `g_bypass_wb`,
    which has no flip-flops at all; writeback is combinational in this
    configuration.  docs/42 section 4.3 records that as a fact about the
    configuration rather than a gap in the campaign.
  * The memories, the fabric and the peripherals.  This campaign is
    about the CORE, because docs/38 section 10 item 4 is a decision
    about the core.  docs/42 section 9 says what that leaves uncovered.
"""

import collections
import os

Site = collections.namedtuple("Site", "stratum name path width")

# Which register file the build under test contains.  The default
# matches hw/soc/flow/ibex_sources.sh's default, and the campaign's
# control 1 -- which compares every site's path and $bits against the
# elaborated design -- is what stops the two from disagreeing silently:
# a `secded` site list against an `upstream` build fails before any
# data point, naming the site.
REGFILE = os.environ.get("FI_REGFILE", "secded")
if REGFILE not in ("secded", "upstream"):
    raise SystemExit("FI_REGFILE must be 'secded' or 'upstream'")

# Everything below hangs off the Ibex instance in soc_top.v.  The
# testbench supplies `dut.u_ibex.` in front of TOP paths and
# `dut.u_ibex.u_ibex_core.` in front of CORE paths, so the strings here
# are the ones a reader can find in hw/soc/gen/*.v by searching.
CORE = "u_ibex_core."

_STRATA_DOC = {
    "regfile": "the 31 architectural general-purpose registers x1..x31",
    "pc_fetch": "the fetch address and the prefetch buffer's request state",
    "fetch_fifo": "the instruction queue between fetch and decode",
    "if_id": "the IF/ID pipeline register: the instruction and its PC",
    "controller": "the main control FSM and its exception and NMI state",
    "id_ctrl": "the ID stage's sequencing and multi-cycle intermediate value",
    "lsu": "the load/store unit's FSM and datapath registers",
    "multdiv": "the RV32M multiplier and divider sequencer",
    "csr_trap": "the machine trap CSRs: mstatus, mepc, mcause, mtvec, mtval, mie, mscratch",
    "csr_pmp": "the PMP configuration and address registers",
    "csr_cnt": "the mcycle and minstret performance counters",
    "csr_debug": "the debug-mode CSRs, which nothing in this SoC can reach",
    "top_ctrl": "ibex_top's own core-busy state, outside ibex_core",
    "regfile_ecc": "the SECDED check bits over x1..x31 and the scrub pointer",
}


def _sites():
    s = []

    # ---- regfile ---------------------------------------------------
    # ibex_register_file_ff.v `g_plain_rf.g_rf_flops[i].rf_reg_q`, one
    # generate instance per architectural register.  x0 is not here:
    # `g_normal_r0` ties it to the zero word and it has no flops.
    for i in range(1, 32):
        s.append(Site(
            "regfile", "x%d" % i,
            "gen_regfile_ff.register_file_i.g_plain_rf.g_rf_flops[%d].rf_reg_q" % i,
            32))

    # ---- pc_fetch --------------------------------------------------
    pf = CORE + "if_stage_i.gen_prefetch_buffer.prefetch_buffer_i."
    for name, width in (("fetch_addr_q", 32), ("stored_addr_q", 32),
                        ("rdata_outstanding_q", 2), ("branch_discard_q", 2),
                        ("discard_req_q", 1), ("valid_req_q", 1)):
        s.append(Site("pc_fetch", name, pf + name, width))

    # ---- fetch_fifo ------------------------------------------------
    ff = pf + "fifo_i."
    for name, width in (("rdata_q", 96), ("instr_addr_q", 31),
                        ("valid_q", 3), ("err_q", 3)):
        s.append(Site("fetch_fifo", name, ff + name, width))

    # ---- if_id -----------------------------------------------------
    ifs = CORE + "if_stage_i."
    for name, width in (("instr_rdata_id_o", 32), ("instr_rdata_alu_id_o", 32),
                        ("pc_id_o", 32), ("instr_rdata_c_id_o", 16),
                        ("instr_expanded_id_o", 16),
                        ("instr_valid_id_q", 1), ("instr_new_id_q", 1),
                        ("instr_is_compressed_id_o", 1),
                        # Two bits, not one: it carries a per-half-word
                        # flag for the compressed decoder.  The width
                        # check in campaign.py is what said so.
                        ("instr_gets_expanded_id_o", 2),
                        ("illegal_c_insn_id_o", 1),
                        ("instr_fetch_err_o", 1),
                        ("instr_fetch_err_plus2_o", 1)):
        s.append(Site("if_id", name, ifs + name, width))

    # ---- controller ------------------------------------------------
    ct = CORE + "id_stage_i.controller_i."
    for name, width in (("ctrl_fsm_cs", 4), ("exc_req_q", 1),
                        ("illegal_insn_q", 1), ("load_err_q", 1),
                        ("store_err_q", 1), ("nmi_mode_q", 1),
                        ("debug_mode_q", 1), ("do_single_step_q", 1),
                        ("enter_debug_mode_prio_q", 1), ("debug_cause_q", 3)):
        s.append(Site("controller", name, ct + name, width))

    # ---- id_ctrl ---------------------------------------------------
    ids = CORE + "id_stage_i."
    for name, path, width in (
            ("id_fsm_q", ids + "id_fsm_q", 1),
            ("branch_jump_set_done_q", ids + "branch_jump_set_done_q", 1),
            ("branch_set_raw_q", ids + "g_branch_set_flop.branch_set_raw_q", 1),
            ("imd_val_q", ids + "imd_val_q", 68)):
        s.append(Site("id_ctrl", name, path, width))

    # ---- lsu -------------------------------------------------------
    ls = CORE + "load_store_unit_i."
    for name, width in (("ls_fsm_cs", 4), ("addr_last_q", 32),
                        ("rdata_q", 24), ("data_type_q", 2),
                        ("rdata_offset_q", 2), ("data_sign_ext_q", 1),
                        ("data_we_q", 1), ("handle_misaligned_q", 1),
                        ("pmp_err_q", 1), ("lsu_err_q", 1),
                        # Five bits of CHERIoT capability-load state that
                        # survive at BaseIsa = RV32I.  They are dead
                        # logic in this configuration and they are
                        # injected anyway, because a flip-flop that is in
                        # the design is a flip-flop an upset can land in,
                        # whatever the architecture thinks of it.
                        # hw/soc/flow/fi_coverage.sh is what found them.
                        ("cap_rx_fsm_q", 3), ("cap_lsw_err_q", 1),
                        ("cheriot_err_q", 1)):
        s.append(Site("lsu", name, ls + name, width))

    # ---- multdiv ---------------------------------------------------
    md = CORE + "ex_block_i.gen_multdiv_fast.multdiv_i."
    for name, width in (("md_state_q", 3), ("div_counter_q", 5),
                        ("op_numerator_q", 32), ("op_quotient_q", 32),
                        ("div_by_zero_q", 1)):
        s.append(Site("multdiv", name, md + name, width))
    # RV32M = 2 (RV32MFast) selects `gen_mult_fast`, whose multiplier
    # sequencer is two bits.  `gen_mult_single_cycle` -- RV32M = 3 --
    # holds a one-bit register of the same name at a different path, and
    # it is not built here.
    s.append(Site("multdiv", "mult_state_q",
                  md + "gen_mult_fast.mult_state_q", 2))

    # ---- csr_trap --------------------------------------------------
    # Widths are ibex_cs_registers.v's `Width` parameter on each
    # ibex_csr instance, not 32: Ibex stores only the bits it
    # implements.  mstatus is 6, mcause is 7, mie is 18.
    cs = CORE + "cs_registers_i."
    for name, inst, width in (
            ("mstatus", "u_mstatus_csr", 6),
            ("mepc", "u_mepc_csr", 32),
            ("mie", "u_mie_csr", 18),
            ("mscratch", "u_mscratch_csr", 32),
            ("mcause", "u_mcause_csr", 7),
            ("mtval", "u_mtval_csr", 32),
            ("mtvec", "u_mtvec_csr", 32),
            ("mstack", "u_mstack_csr", 3),
            ("mstack_epc", "u_mstack_epc_csr", 32),
            ("mstack_cause", "u_mstack_cause_csr", 7),
            ("mcounteren", "u_mcounteren_csr", 3),
            ("cpuctrlsts", "u_cpuctrlsts_part_csr", 8)):
        s.append(Site("csr_trap", name, cs + inst + ".rdata_q", width))
    s.append(Site("csr_trap", "priv_lvl_q", cs + "priv_lvl_q", 2))

    # ---- csr_pmp ---------------------------------------------------
    # Four regions, PMPNumRegions = 4 in soc_top.v, which is the number
    # docs/09 part B track 3 names for option S2.
    for i in range(4):
        g = cs + "g_pmp_registers.g_pmp_csrs[%d]." % i
        s.append(Site("csr_pmp", "pmpcfg%d" % i, g + "u_pmp_cfg_csr.rdata_q", 6))
        s.append(Site("csr_pmp", "pmpaddr%d" % i,
                      g + "u_pmp_addr_csr.rdata_q", 32))
    s.append(Site("csr_pmp", "mseccfg",
                  cs + "g_pmp_registers.u_pmp_mseccfg.rdata_q", 3))

    # ---- csr_cnt ---------------------------------------------------
    s.append(Site("csr_cnt", "mcycle", cs + "mcycle_counter_i.counter_q", 64))
    s.append(Site("csr_cnt", "minstret",
                  cs + "minstret_counter_i.counter_q", 64))
    s.append(Site("csr_cnt", "mcountinhibit",
                  cs + "mcountinhibit_q", 3))

    # ---- csr_debug -------------------------------------------------
    # The debug-mode CSRs.  This SoC ties `debug_req_i` low and has no
    # debug module (docs/39 section 8 leaves the region reserved and
    # faulting), so nothing can ever enter debug mode and nothing reads
    # these.  They are 128 flip-flops of the core all the same, they are
    # a twentieth of it, and a campaign that left them out would be
    # reporting a rate over a core it had not finished looking at.
    for name, inst in (("dcsr", "u_dcsr_csr"), ("depc", "u_depc_csr"),
                       ("dscratch0", "u_dscratch0_csr"),
                       ("dscratch1", "u_dscratch1_csr")):
        s.append(Site("csr_debug", name, cs + inst + ".rdata_q", 32))

    # ---- regfile_ecc -----------------------------------------------
    # The check bits docs/43 adds, and the scrub pointer that walks
    # them.  They are a stratum of their own rather than part of
    # `regfile` for two reasons that are both about not hiding
    # something.  They are new flip-flops the design did not have, so
    # folding them into `regfile` would change that stratum's measured
    # rate for two unrelated reasons at once -- the protection and the
    # extra area -- and neither would be separable afterwards.  And
    # they are 248 bits that an upset can land in exactly as it can
    # land in the data, so a campaign that protected the data and did
    # not measure the protection would be reporting on a design it had
    # not finished looking at.
    if REGFILE == "secded":
        for i in range(1, 32):
            s.append(Site(
                "regfile_ecc", "x%d_chk" % i,
                "gen_regfile_ff.register_file_i.g_plain_rf."
                "g_rf_flops[%d].g_chk.rf_chk_q" % i,
                8))
        s.append(Site(
            "regfile_ecc", "scrub_ptr",
            "gen_regfile_ff.register_file_i.g_plain_rf.g_secded."
            "g_scrub.ptr_q", 5))

    # ---- top_ctrl --------------------------------------------------
    # Outside ibex_core: the multi-bit-encoded busy state ibex_top holds
    # to drive its clock gate and core_sleep_o.
    s.append(Site("top_ctrl", "core_busy_q", "core_busy_q", 4))

    return s


SITES = _sites()

STRATA = []
for _s in SITES:
    if _s.stratum not in STRATA:
        STRATA.append(_s.stratum)

STRATUM_DOC = _STRATA_DOC


def stratum_sites(name):
    return [s for s in SITES if s.stratum == name]


def stratum_bits(name):
    return sum(s.width for s in stratum_sites(name))


def emit_vh(path):
    """Write the Verilog the testbench includes.

    Two things come out of one list: a `case` that performs the deposit
    and reports the width it found, and a dump of every site so the
    campaign can check the elaborated design against this table.
    """
    lines = []
    lines.append("// GENERATED by hw/soc/fi/targets.py -- do not edit.")
    lines.append("// %d sites in %d strata." % (len(SITES), len(STRATA)))
    lines.append("")
    lines.append("`define FI_SITE_COUNT %d" % len(SITES))
    lines.append("")
    lines.append("`define FI_DEPOSIT_CASES \\")
    for i, s in enumerate(SITES):
        lines.append(
            "  %d: begin fi_w = $bits(%s); fi_before = %s; "
            "%s = %s ^ fi_bitmask; fi_after = %s; fi_hit = 1'b1; end \\"
            % (i, _full(s), _full(s), _full(s), _full(s), _full(s)))
    lines.append("")
    lines.append("`define FI_DUMP_SITES \\")
    for i, s in enumerate(SITES):
        # The path printed is the FULL one the case statement above
        # uses, prefix included, so the campaign's comparison covers
        # where the site hangs off the design and not only its tail.
        lines.append(
            "  $display(\"SITE %d %s %s %%0d %s\", $bits(%s)); \\"
            % (i, s.stratum, s.name, _full(s), _full(s)))
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _full(site):
    return "dut.u_ibex." + site.path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        emit_vh(sys.argv[1])
    for name in STRATA:
        n = stratum_sites(name)
        print("%-12s %3d sites %5d bits   %s"
              % (name, len(n), stratum_bits(name), STRATUM_DOC[name]))
    print("%-12s %3d sites %5d bits" % ("TOTAL", len(SITES),
                                        sum(s.width for s in SITES)))
