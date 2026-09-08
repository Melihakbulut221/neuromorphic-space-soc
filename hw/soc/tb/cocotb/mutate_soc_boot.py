#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Mutation evidence for the boot register suite (docs/68).

    python3 hw/soc/tb/cocotb/mutate_soc_boot.py

Each mutation is a small edit to a COPY of hw/soc/rtl/soc_boot.v, built
with Makefile.soc_boot's parameters, and the claim is that the suite
FAILS on every one of them. A suite that passes on a mutant is a suite
whose green result is narrower than what it examined -- the shape
docs/41 section 6.6 counts.

The mutations are the wrong-way-round versions of the arguments in
soc_boot.v's header, and every one of them is a design that WORKS in the
ordinary case. That is the point: each is a boot flow that boots
correctly on a healthy part and fails only in the case the block exists
for.

  cnt_writable   an APB write to BSTAT loads the boot counter. This is
                 the mutation that matters: it is a counter the failing
                 software can clear, which is soc_wdog.v W1's rejected
                 design one level up. A part with it boots identically
                 and retries for ever.
  cnt_wraps      the saturation is removed. A part that has rebooted
                 2^CNT_W times drops back below the attempt limit and
                 starts the ladder again -- a boot loop with no end and
                 no report.
  cnt_por_zero   the power-on boot is counted, so BSTAT.CNT reads one on
                 a part that has just been powered up. Every attempt
                 limit is then off by one and the last boot the loader
                 attempts is not the one the watchdog escalated on.
  cnt_on_level   the counter increments on the LEVEL of the system reset
                 rather than on its release, so a reset held for n
                 cycles counts n boots.
  strap_live     the straps are resampled every cycle instead of once. A
                 pin that can change a boot decision after the boot
                 began is soc_wdog.v W1's hardware back door.
  strap_sysrst   the strap sample is redone on a SYSTEM reset. The
                 sample then belongs to the boot and not to the power
                 cycle, and a glitching pin changes the boot source
                 between attempts.
  rpt_sysrst     the report and the epoch are put in the system reset
                 domain. They are then erased by the reset they exist to
                 describe, which is exactly docs/40 section 7.2's
                 operator-facing failure: a machine that reboots for no
                 discoverable reason.
  last_off_by_one the LAST flag is computed against LIMIT rather than
                 LIMIT-1, so the loader's last attempt is one boot late.

docs/69 adds five, and they are all mutations of B1. Each is a
protection that LOOKS present -- three banks, a voter, a report -- and
is not, which is the shape docs/41 section 6.6 counts and docs/43
section 9.4 found twenty formal tasks staying green on:

  vote_two       the voter is fed replica A twice, so it is a duplex
                 with a spare. An upset in A now WINS the vote and one
                 in C is invisible. Nothing about the flip-flop count
                 changes, which is why this is a suite mutation and not
                 a census one.
  report_silent  the mismatch is corrected and never announced --
                 docs/43 section 6.5's complaint, built.
  report_clearable a write to BSTAT clears TMRERR and TMRCNT. docs/41
                 section 5.3: a record software can erase is a record an
                 upset can erase.
  report_wraps   TMRCNT's saturation is removed, so a part with sixteen
                 masked upsets reports fewer than a part with one.
  sys_unprotected  sys_q goes back to being a plain flip-flop outside
                 the word, which is the FIRST VERSION OF THIS DESIGN.
                 It is here because the campaign is what rejected it and
                 a mutation is the only way to keep that rejection
                 checked. NOT caught by this suite, by construction --
                 the consequence is a spurious boot count from an upset,
                 and there is no upset in a functional run -- and, the
                 surprise, NOT CAUGHT BY THE CAMPAIGN EITHER: its target
                 list is derived from the same field layout, so a field
                 that leaves the word leaves the target list too and the
                 injection lands on a bit nothing reads. What catches it
                 is a textual guard on the RTL's own declarations, in
                 sw/tests/test_soc_boot_guards.py. See EXPECTED_UNCAUGHT.

Every mutation is applied to the RTL text and asserted to have changed
it; a mutation that does not apply is a hard failure, not a pass.

ONE MUTATION IS EXPECTED TO SURVIVE and it is listed as such rather than
quietly counted. `sys_unprotected` is a design this suite cannot tell
apart from the shipped one, because the difference is what happens under
an upset and there are no upsets in a functional run. Recording it here
-- with the suite that DOES catch it named -- is the alternative to
either deleting the mutation or letting the script's headline number be
wrong about what was examined. docs/41 section 6.6's list of eight green
checks read wider than what they examined is the reason.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = os.path.normpath(os.path.join(HERE, "..", "..", "rtl", "soc_boot.v"))

CNT_BLOCK = """    prot_n[P_SYS] = rst_ni;
    if (rst_ni && !sys_q) begin
      if (!armed_q)     prot_n[P_ARMED]        = 1'b1;
      else if (~&cnt_q) prot_n[P_CNT +: CNT_W] =
                            cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};
    end"""

STRAP_BLOCK = """    if (!valid_q) begin
      if (dly == 2'd2) begin
        prot_n[P_STRAP +: NSTRAP] = sync1;
        prot_n[P_WDIS]            = wsync1;
        prot_n[P_VALID]           = 1'b1;
      end else begin
        prot_n[P_DLY +: 2] = dly + 2'd1;
      end
    end"""

REPORT_BLOCK = """    prot_n[P_TMRERR] = tmr_err | prot_mismatch;
    if (prot_mismatch && ~&tmr_count)
      prot_n[P_TMRCNT +: TMC_W] = tmr_count + {{(TMC_W-1){1'b0}}, 1'b1};"""

MUTATIONS = {
    "cnt_writable": [
        (CNT_BLOCK,
         CNT_BLOCK + """
    if (wr && (paddr_i == REG_BSTAT))
      prot_n[P_CNT +: CNT_W] = pwdata_i[CNT_W-1:0];"""),
    ],
    "cnt_wraps": [
        ("      else if (~&cnt_q) prot_n[P_CNT +: CNT_W] =",
         "      else              prot_n[P_CNT +: CNT_W] ="),
    ],
    "cnt_por_zero": [
        ("      if (!armed_q)     prot_n[P_ARMED]        = 1'b1;\n"
         "      else if (~&cnt_q) prot_n[P_CNT +: CNT_W] =",
         "      prot_n[P_ARMED] = 1'b1;\n"
         "      if (~&cnt_q)      prot_n[P_CNT +: CNT_W] ="),
    ],
    "cnt_on_level": [
        ("    if (rst_ni && !sys_q) begin",
         "    if (!rst_ni) begin"),
    ],
    "strap_live": [
        (STRAP_BLOCK,
         """    prot_n[P_STRAP +: NSTRAP] = sync1;
    prot_n[P_WDIS]            = wsync1;
    if (!valid_q) begin
      if (dly == 2'd2) prot_n[P_VALID]    = 1'b1;
      else             prot_n[P_DLY +: 2] = dly + 2'd1;
    end"""),
    ],
    "strap_sysrst": [
        (STRAP_BLOCK,
         """    if (!valid_q || !rst_ni) begin
      prot_n[P_STRAP +: NSTRAP] = sync1;
      prot_n[P_WDIS]            = wsync1;
      prot_n[P_VALID]           = 1'b1;
    end"""),
    ],
    "rpt_sysrst": [
        ("""  reg [31:0] brpt_q, epoch_q;
  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin""",
         """  reg [31:0] brpt_q, epoch_q;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin"""),
    ],
    "last_off_by_one": [
        ("  wire last_attempt = (cnt_q >= (LIMIT_C - {{(CNT_W-1){1'b0}}, 1'b1}));",
         "  wire last_attempt = (cnt_q >= LIMIT_C);"),
    ],
    # ---- docs/69, B1 --------------------------------------------------
    "vote_two": [
        ("        .in_c     (qc),", "        .in_c     (qa),"),
    ],
    "report_silent": [
        (REPORT_BLOCK,
         """    prot_n[P_TMRERR] = tmr_err;"""),
    ],
    "report_clearable": [
        (REPORT_BLOCK,
         REPORT_BLOCK + """
    if (wr && (paddr_i == REG_BSTAT)) begin
      prot_n[P_TMRERR]          = 1'b0;
      prot_n[P_TMRCNT +: TMC_W] = {TMC_W{1'b0}};
    end"""),
    ],
    "report_wraps": [
        ("    if (prot_mismatch && ~&tmr_count)",
         "    if (prot_mismatch)"),
    ],
    "sys_unprotected": [
        ("  wire              sys_q     = prot[P_SYS];",
         "  reg               sys_q;\n"
         "  always @(posedge clk_i or negedge rst_por_ni)\n"
         "    if (!rst_por_ni) sys_q <= 1'b0; else sys_q <= rst_ni;"),
        ("    prot_n[P_SYS] = rst_ni;\n", ""),
    ],
}

# Mutations this suite is expected NOT to catch, with what does catch
# them. A mutation that moves out of this set is as much a finding as
# one that moves into it, so the script checks BOTH directions.
EXPECTED_UNCAUGHT = {
    "sys_unprotected":
        "sw/tests/test_soc_boot_guards.py::"
        "test_every_flip_flop_outside_the_protected_word_is_one_that_"
        "was_decided -- and NOT by the campaign, which was the first "
        "answer and was wrong: running test_soc_boot_fi.py against this "
        "mutant passes 4 of 4, because the campaign derives its targets "
        "from the same field layout the mutation edits, so the injection "
        "lands on a bit nothing reads and comes back CORRECTED",
}


def run_suite(src, tag):
    env = dict(os.environ)
    build = os.path.join(HERE, "sim_build_mutb_" + tag)
    results = os.path.join(HERE, "results_mutb_%s.xml" % tag)
    if os.path.exists(results):
        os.remove(results)
    cmd = ["make", "-f", "Makefile.soc_boot",
           "SOC_BOOT_SRC=" + src, "SIM_BUILD=" + build,
           "COCOTB_RESULTS_FILE=results_mutb_%s.xml" % tag]
    subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)
    if not os.path.exists(results):
        return None, None
    root = ET.parse(results).getroot()
    cases = [e for e in root.iter() if e.tag.endswith("testcase")]
    failed = [c.get("name") for c in cases
              if any(ch.tag.endswith(("failure", "error")) for ch in c)]
    shutil.rmtree(build, ignore_errors=True)
    os.remove(results)
    return len(cases), failed


def main():
    text = open(RTL).read()
    tmp = tempfile.mkdtemp(prefix="mutate_soc_boot_")
    caught = 0
    bad = []
    print("%-16s %6s  %s" % ("mutation", "tests", "failing tests"))
    for name, edits in MUTATIONS.items():
        mutant = text
        for old, new in edits:
            if old not in mutant:
                sys.exit("mutation %s does not apply: %r not in soc_boot.v"
                         % (name, old))
            mutant = mutant.replace(old, new)
        assert mutant != text
        path = os.path.join(tmp, "soc_boot_%s.v" % name)
        open(path, "w").write(mutant)
        n, failed = run_suite(path, name)
        if n is None:
            print("%-16s %6s  %s" % (name, "-", "no results: the build failed"))
            caught += 1
            continue
        print("%-16s %6d  %s" % (name, n, ", ".join(failed) if failed else "NONE"))
        if failed:
            caught += 1
        if name in EXPECTED_UNCAUGHT and failed:
            print("  ** %s was expected to survive this suite and did not; "
                  "the note in EXPECTED_UNCAUGHT is now wrong" % name)
            bad.append(name)
        elif name not in EXPECTED_UNCAUGHT and not failed:
            bad.append(name)
    shutil.rmtree(tmp, ignore_errors=True)
    want = len(MUTATIONS) - len(EXPECTED_UNCAUGHT)
    print("caught %d of %d; %d expected to survive this suite:" %
          (caught, len(MUTATIONS), len(EXPECTED_UNCAUGHT)))
    for k, v in EXPECTED_UNCAUGHT.items():
        print("  %-16s caught instead by %s" % (k, v))
    if bad:
        print("UNEXPECTED: %s" % ", ".join(bad))
    return 0 if (caught == want and not bad) else 1


if __name__ == "__main__":
    sys.exit(main())
