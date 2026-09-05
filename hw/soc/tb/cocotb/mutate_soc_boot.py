#!/usr/bin/env python3
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

Every mutation is applied to the RTL text and asserted to have changed
it; a mutation that does not apply is a hard failure, not a pass.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
RTL = os.path.normpath(os.path.join(HERE, "..", "..", "rtl", "soc_boot.v"))

CNT_BLOCK = """      sys_q <= rst_ni;
      if (rst_ni && !sys_q) begin
        if (!armed_q)        armed_q <= 1'b1;
        else if (~&cnt_q)    cnt_q   <= cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};
      end"""

STRAP_BLOCK = """      if (!valid_q) begin
        if (dly == 2'd2) begin
          strap_q <= sync1;
          wdis_q  <= wsync1;
          valid_q <= 1'b1;
        end else begin
          dly <= dly + 2'd1;
        end
      end"""

MUTATIONS = {
    "cnt_writable": [
        (CNT_BLOCK,
         CNT_BLOCK + """
      if (wr && (paddr_i == REG_BSTAT)) cnt_q <= pwdata_i[CNT_W-1:0];"""),
    ],
    "cnt_wraps": [
        ("        else if (~&cnt_q)    cnt_q   <= cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};",
         "        else                 cnt_q   <= cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};"),
    ],
    "cnt_por_zero": [
        ("        if (!armed_q)        armed_q <= 1'b1;\n"
         "        else if (~&cnt_q)    cnt_q   <= cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};",
         "        armed_q <= 1'b1;\n"
         "        if (~&cnt_q)         cnt_q   <= cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};"),
    ],
    "cnt_on_level": [
        ("      if (rst_ni && !sys_q) begin",
         "      if (!rst_ni) begin"),
    ],
    "strap_live": [
        (STRAP_BLOCK,
         """      strap_q <= sync1;
      wdis_q  <= wsync1;
      if (!valid_q) begin
        if (dly == 2'd2) valid_q <= 1'b1;
        else             dly <= dly + 2'd1;
      end"""),
    ],
    "strap_sysrst": [
        (STRAP_BLOCK,
         """      if (!valid_q || !rst_ni) begin
        strap_q <= sync1;
        wdis_q  <= wsync1;
        valid_q <= 1'b1;
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
    shutil.rmtree(tmp, ignore_errors=True)
    print("caught %d of %d" % (caught, len(MUTATIONS)))
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
