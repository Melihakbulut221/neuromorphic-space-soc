#!/usr/bin/env python3
"""The strata and the injection sites of the NPU-connection campaign of
docs/52, written down ONCE.

WHY THIS FILE EXISTS RATHER THAN TWO LISTS

The same reason hw/soc/fi/targets.py exists, and the same failure it
prevents: the campaign needs the target list in Verilog, where a
hierarchical name must be written literally, and in Python, where the
classifier has to know which stratum a record belongs to.  Two copies of
that list is one copy too many.  `emit_vh()` generates the Verilog, the
testbench dumps what it ELABORATED -- index, stratum, name, `$bits` and
full path -- and `npu_campaign.py` control 1 compares all five against
this table before it injects anything.

THREE POPULATIONS, AND THEY ARE NOT EQUIVALENT

docs/51 section 14 item 1 records what is unprotected in this block, and
the list is not homogeneous.  An upset in the serial transport corrupts
ONE REGISTER ACCESS.  An upset in the event path corrupts AN INFERENCE.
An upset in the cause register corrupts WHAT THE OPERATOR IS TOLD.  Those
are three different consequences and they lead to three different
decisions, so they are three different populations and the campaign
samples each of them equally rather than sampling the block uniformly
and reporting an average that describes none of them.

docs/42 section 4.1 makes the same argument for the core, and docs/41
section 3.1 makes the criterion explicit: rank by PERSISTENCE TIMES
SILENCE, not by how important the register sounds.  The strata below are
drawn so that a stratum is a thing about which one could make a
different hardening decision.

AND ONE OF THEM IS INSIDE THE FROZEN DIE

`hw/rtl/pilot_top.v` is INSTANTIATED in this design, not copied
(docs/51 section 3), so its flip-flops are reachable from this testbench.
Injecting into them is legitimate as MEASUREMENT -- docs/16 already did,
on the block alone -- but the records must be separable, because they
lead to different decisions:

  * an upset in the connection is a property of a design that is STILL
    OPEN.  It can be hardened.
  * an upset in the die is a property of SILICON ALREADY COMMITTED.
    docs/34 pins the submission by blob hash and the TTIHP26b shuttle
    closes 2026-09-21.  Nothing this campaign finds there can be fixed
    in that die.

So `die_ser` is a stratum of its own and every report prints it apart
from the rest.  It is deliberately NOT a re-measurement of the die:
docs/16 did that, on the whole block, with 255 injections and its own
target list.  What this stratum is, is the die's OWN HALF OF THE SERIAL
TRANSPORT -- the synchronizers and the 40-bit shift engine that
`soc_npu_ser.v` talks to -- so that the same 40-bit frame, implemented
twice on the two sides of one pin boundary, is measured with the same
draws.  Nothing else in the die is a target here and docs/52 section 9
says what that leaves uncovered.

WHAT IS DELIBERATELY NOT HERE

  * The CORE, the fabric, the memories, the CLINT, the timers, the UART
    and the watchdog's own state.  docs/42 is the core's campaign and
    docs/41 section 8 is the watchdog's.  This one is about the block
    between them, which is the block docs/51 section 18 says is the
    first in the SoC to sit between two measured things and be itself
    unmeasured.
  * The rest of `pilot_top`: its LIF datapath, its weight memory, its
    configuration bank, its own event queues and its scrubber.  docs/16
    measures all of them and docs/32 confirms the RTL result against the
    netlist.
"""

import collections
import os
import re

Site = collections.namedtuple("Site", "stratum name path width")

_RTL = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "rtl", "soc_npu.v"))


def _lp_int(name):
    """One `localparam integer <name> = <literal>;` out of soc_npu.v.

    PARSED AND NOT WRITTEN DOWN.  docs/52's classifier spelled the cause
    register's fault bits out one at a time; docs/55 added five more, and
    a hand-written copy would have gone on reporting every one of them as
    "silent to every hardware channel" -- a campaign flattering its own
    hardening, which is the exact shape docs/41 section 6.6's list is
    made of.  A literal that moves in the RTL has to move here with it,
    and the only way to guarantee that is to read it from there.
    """
    with open(_RTL) as f:
        text = f.read()
    m = re.search(r"localparam\s+integer\s+" + name + r"\s*=\s*(\d+)\s*;", text)
    if not m:
        raise RuntimeError(
            "no `localparam integer %s = <literal>;` in %s" % (name, _RTL))
    return int(m.group(1))


# The cause register's width, and the first STICKY bit in it.  Both are
# literals in soc_npu.v; everything below is arithmetic on them.
NCAUSE = _lp_int("NCAUSE")
C_STICKY0 = _lp_int("C_INJ_OVF")
NSTICKY = NCAUSE - C_STICKY0

# The five sticky bits docs/55 added, by name, for the controls and the
# report.  Parsed for the same reason NCAUSE is.
C_SER_TO = _lp_int("C_SER_TO")
C_WIN_TO = _lp_int("C_WIN_TO")
C_Q_COR = _lp_int("C_Q_COR")
C_Q_DET = _lp_int("C_Q_DET")
C_CFG_TMR = _lp_int("C_CFG_TMR")

# soc_npu.v's protected word, docs/55 H3:
#   P_IN_EN (1) + P_OUT_EN (1) + NSTICKY + NCAUSE
# The RTL writes it as `P_MASK + NCAUSE`, which is not a literal, so it
# is re-derived here from the two that are -- and the testbench's own
# `$bits` dump is what checks the derivation, in npu_campaign.py control
# 1, which fails on a one-bit disagreement.
PROT_W = 2 + NSTICKY + NCAUSE

# Everything hangs off the NPU subsystem in soc_top.v.  The testbench
# supplies `dut.u_npu.` in front of every path below, so the strings here
# are the ones a reader can find in hw/soc/rtl/soc_npu.v,
# hw/soc/rtl/soc_npu_ser.v and hw/rtl/aer_fifo.v by searching.
SER = "u_ser."
INJ = "u_inj."
CAP = "u_cap."
DIE = "u_node0."

# aer_fifo at DEPTH = 8: AW = 3, PW = AW + 1 = 4, WIDTH = 16, DROP_W = 8.
# Both queues are instantiated at those parameters in soc_npu.v.  The
# numbers are here rather than imported because the testbench's own dump
# is what checks them -- a DEPTH that changed shows up as a width
# disagreement in control 1 and not as a wrong comment.
Q_DEPTH = 8
Q_WIDTH = 16
Q_PW = 4

_STRATA_DOC = {
    "ser": "the SoC's serial transport: the 40-bit shift engine and its "
           "phase counters",
    "die_ser": "the FROZEN die's own half of the same transport: its pin "
               "synchronizers and its 40-bit shift engine",
    "window": "the node register window's bus face: the captured request, "
              "the FSM and the response",
    "cfgreg": "the NPUCFG control and cause registers: what the operator "
              "is told",
    "engine": "the event engine's FSM and datapath, and the show-ahead "
              "adapter in front of the capture queue",
    "evq_data": "the two SoC-side queues' stored event words, their "
                "entry-parity check field and the read capture",
    "evq_ptr": "the two SoC-side queues' triple-redundant pointers, their "
               "dual-rail rd_valid and their drop counters",
}

# Which population each stratum belongs to.  docs/52 section 4 ranks by
# CONSEQUENCE and the consequence is a property of the population, not of
# the flip-flop count.
POPULATION = {
    "ser": "transport",
    "die_ser": "transport (frozen die)",
    "window": "register path",
    "cfgreg": "register path",
    "engine": "event path",
    "evq_data": "event path",
    "evq_ptr": "event path",
}

# Which strata are inside hw/rtl/, and therefore inside silicon that
# docs/34 has frozen.  Every report separates them, because a finding in
# one is a design change and a finding in the other is not.
FROZEN = ("die_ser",)


def _sites():
    s = []

    # ---- ser: the SoC's serial transport ---------------------------
    # soc_npu_ser.v.  134 flip-flops, which is the number docs/51
    # section 11 measured with Yosys on the same module -- an
    # independent check that this list is the whole of it.
    # `guard` and `timeout_o` are docs/55's frame bound and are targets
    # like anything else.  THE GUARD IS UNPROTECTED STATE WHOSE UPSET
    # ABORTS A HEALTHY FRAME, which is a new failure the hardening
    # introduced, and a campaign that did not draw into it would be
    # measuring the mechanism's benefit without its cost.  docs/55
    # section 8 reports what the draws found there.
    for name, width in (("state", 2), ("tx", 40), ("rx", 32),
                        ("bit_cnt", 6), ("hcnt", 2), ("tick", 16),
                        ("guard", 8), ("timeout_o", 1),
                        ("done_o", 1), ("rdata_o", 32),
                        ("ser_sck_o", 1), ("ser_cs_n_o", 1),
                        ("ser_mosi_o", 1)):
        s.append(Site("ser", "ser_" + name, SER + name, width))

    # ---- die_ser: the frozen die's half of the same transport ------
    # hw/rtl/pilot_top.v sections 2 and 3.  The two-flop synchronizers
    # on all four pins, the edge detect, and the shift engine the frame
    # is decoded by.  READ AND NOT MODIFIED, exactly as the module is.
    for name, width in (("sck_s", 2), ("csn_s", 2), ("mosi_s", 2),
                        ("sck_q", 1),
                        ("bit_cnt", 6), ("rx_sh", 32), ("tx_sh", 32),
                        ("cmd_wr", 1), ("cmd_addr", 7),
                        ("rd_strobe", 1), ("wr_strobe", 1)):
        s.append(Site("die_ser", "die_" + name, DIE + name, width))

    # ---- window: the node register window's bus face ---------------
    # The captured request, the four-state FSM and the response.  An
    # upset here corrupts ONE register access -- and docs/51 section
    # 13 defect 1 records what a lost or duplicated response looks like
    # from the CPU: a read after a write returning zero.
    #
    # `win_guard` is docs/55's response bound, nine flip-flops, and
    # `win_out` is the flag that arms it: one bit saying the fabric has
    # granted a request this slave has not yet answered.  Both carry the
    # same asymmetry `ser_guard` does -- an upset in either FAILS A
    # HEALTHY ACCESS with a bus error rather than hanging one, and an
    # upset that CLEARS `win_out` while a request is outstanding re-opens
    # the hang the bound closes.  They are in the campaign for that
    # reason: a hardening measured without its own new state is a
    # hardening measured for its benefit and not its cost.
    for name, width in (("win_state", 2), ("win_start", 1), ("win_we", 1),
                        ("win_addr", 7), ("win_wdata", 32),
                        ("win_err_q", 1), ("win_guard", 9), ("win_out", 1),
                        ("rvalid_o", 1), ("rdata_o", 32), ("err_o", 1),
                        ("ser_owner_win", 1)):
        s.append(Site("window", name, name, width))

    # ---- cfgreg: the control and cause registers -------------------
    # docs/41 section 3.1's criterion applies to these exactly: they are
    # PERSISTENT -- written once by software and never rewritten by the
    # block -- and before docs/55 their corruption was SILENT.  docs/52
    # measured what that cost: a FALSE FAULT REPORT in 16 of 100 draws,
    # the highest per-bit consequence anywhere in that campaign.
    #
    # THE POPULATION OF THIS STRATUM IS NOT THE ONE docs/52 DREW FROM,
    # and that is the hardening rather than a change of method.  Thirteen
    # plain flip-flops became a PROT_W = 21 word held in three
    # soc_tmr_bank replicas, plus the two self-clearing pulses that
    # docs/41 section 3.1's own rule leaves out of the bank.  A directed
    # replay of docs/52's cfgreg records is therefore impossible -- the
    # paths no longer exist -- and docs/55 section 9 says so where it
    # compares the two.
    #
    # THE TARGETS ARE THE REPLICA STORAGE AND NEVER THE VOTED WIRE.
    # `soc_tmr_bank`'s `bits` is what a flip-flop holds; `q_o` is a
    # continuously driven function of it, and a deposit there would be
    # overwritten in the same delta cycle and report nothing about the
    # replicas.  docs/41 section 8.1 records this campaign's ancestor
    # doing exactly that twice, and control 1b in npu_campaign.py now
    # asserts it for this stratum as well as for evq_ptr.
    for r in ("a", "b", "c"):
        s.append(Site("cfgreg", "cfg_%s" % r,
                      "g_cfg_tmr.u_cfg_%s.bits" % r, PROT_W))
    for name, width in (("flush_pulse", 1), ("scrub_pulse", 1)):
        s.append(Site("cfgreg", name, name, width))

    # ---- engine: the event engine and the show-ahead adapter -------
    # The FSM that decides which transport an event takes, the word in
    # flight, the AER pin drivers, the two event counters, and the
    # one-entry show-ahead register in front of the capture queue.
    for name, width in (("ev_state", 4), ("ev_word", 16), ("ev_wait", 4),
                        ("ev_start", 1), ("ev_we", 1), ("ev_addr", 7),
                        ("inj_rd_en", 1),
                        ("aer_in_stb", 1), ("aer_in_tick", 1),
                        ("aer_in_addr", 4),
                        ("cap_wr_en", 1), ("cap_wr_data", 16),
                        ("cnt_in", 16), ("cnt_out", 16),
                        ("oh_valid", 1), ("oh_data", 16), ("oh_req", 1),
                        ("cap_rd_en", 1)):
        s.append(Site("engine", name, name, width))
    # ev_wdata's upper half is loaded only from a constant zero, so
    # synthesis removes it (hw/soc/flow/fi_npu_coverage.sh reports the
    # arithmetic).  The low half is the event word on its way to the
    # die's EVQ_IN register and is injected here; the full 32-bit
    # register is what the RTL declares and what `$bits` will report, so
    # the width below is 32 and the coverage census is where the
    # difference is named rather than hidden.
    s.append(Site("engine", "ev_wdata", "ev_wdata", 32))

    # ---- evq_data: the queues' stored words and their parity -------
    # THIS IS THE ONE PART OF THE CONNECTION THAT CARRIES PROTECTION,
    # and it is inherited rather than designed: both queues are
    # hw/rtl/aer_fifo.v, so every stored entry has an even-parity bit
    # and a failed check DISCARDS the entry and raises `par_err`.
    # docs/16 section 6.2 measured the same storage inside the die.
    #
    # One site per queue slot, because a memory is not one register: a
    # campaign that injected into `mem` as a whole would be injecting
    # into a 128-bit word that nothing reads at once.
    for q, tag in ((INJ, "inj"), (CAP, "cap")):
        for i in range(Q_DEPTH):
            s.append(Site("evq_data", "%s_mem%d" % (tag, i),
                          "%smem[%d]" % (q, i), Q_WIDTH))
        s.append(Site("evq_data", "%s_par" % tag, q + "u_par.bits", Q_DEPTH))
        s.append(Site("evq_data", "%s_rd_data" % tag, q + "rd_data", Q_WIDTH))

    # ---- evq_ptr: the voted pointers and the dual-rail flag --------
    # Three replicas each of the write and the read pointer, per queue,
    # each a separate module instance so that `opt_merge` cannot fold
    # them (aer_fifo.v's own header measures that).  The campaign
    # injects into the REPLICA STORAGE and never into the voted wire --
    # docs/41 section 8.1 records this campaign's ancestor depositing
    # into a continuously driven voter output and reporting the result
    # as if it said something about the replicas, and
    # `test_no_target_is_a_voted_wire` in npu_campaign.py control 1b
    # asserts that no path here ends in one.
    for q, tag in ((INJ, "inj"), (CAP, "cap")):
        for p in ("wptr", "rptr"):
            for r in ("a", "b", "c"):
                s.append(Site("evq_ptr", "%s_%s_%s" % (tag, p, r),
                              "%su_%s_%s.bits" % (q, p, r), Q_PW))
        for r in ("a", "b"):
            s.append(Site("evq_ptr", "%s_rdv_%s" % (tag, r),
                          "%su_rdv_%s.bits" % (q, r), 1))
    # The drop counter.  aer_fifo carries it and soc_npu.v surfaces the
    # injection queue's at NPUCFG.CNT_DROP; the capture queue's is
    # unconnected, which is itself a finding docs/52 section 8 reports.
    s.append(Site("evq_ptr", "inj_drop_cnt", INJ + "drop_cnt", 8))
    s.append(Site("evq_ptr", "cap_drop_cnt", CAP + "drop_cnt", 8))

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


def connection_bits():
    """Every bit this WORK added, excluding the frozen die."""
    return sum(s.width for s in SITES if s.stratum not in FROZEN)


def _full(site):
    return "dut.u_npu." + site.path


def emit_vh(path):
    """Write the Verilog the testbench includes.

    Two things come out of one list: a `case` that performs the deposit
    and reports the width it found, and a dump of every site so the
    campaign can check the elaborated design against this table.
    """
    lines = []
    lines.append("// GENERATED by hw/soc/fi/npu_targets.py -- do not edit.")
    lines.append("// %d sites in %d strata, %d bits."
                 % (len(SITES), len(STRATA), sum(s.width for s in SITES)))
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
        # The FULL path, prefix included, so the campaign's comparison
        # covers where the site hangs off the design and not only its
        # tail.
        lines.append(
            "  $display(\"SITE %d %s %s %%0d %s\", $bits(%s)); \\"
            % (i, s.stratum, s.name, _full(s), _full(s)))
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        emit_vh(sys.argv[1])
    for name in STRATA:
        n = stratum_sites(name)
        print("%-9s %-22s %3d sites %5d bits   %s"
              % (name, POPULATION[name], len(n), stratum_bits(name),
                 STRATUM_DOC[name]))
    print("%-9s %-22s %3d sites %5d bits"
          % ("TOTAL", "", len(SITES), sum(s.width for s in SITES)))
    print("%-9s %-22s %3s       %5d bits  (the frozen die excluded)"
          % ("CONNECT", "", "", connection_bits()))
