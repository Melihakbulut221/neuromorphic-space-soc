"""Textual guards for the NPU connection.

These are the half of the checking that a simulation cannot do, and they
exist for the same reason `sw/tests/test_memmap.py` does: the cocotb
suite and the formal job check BEHAVIOUR, and neither can notice that a
constant has been copied instead of generated, that the frozen directory
has been written to, or that the design has grown a second copy of a
register map. Nothing here simulates anything.

The complementary half is stated in `docs/51-npu-integration.md` section
10, along with what neither half covers.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_soc_npu_guards.py
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sw"))

from golden.memmap_gen import (APB_SLOTS, IRQ_SOURCES,      # noqa: E402
                               PORTS, REGIONS, SPARE_FAST_LINES)
from golden.regmap_gen import ADDR                        # noqa: E402

SOC_RTL = ROOT / "hw" / "soc" / "rtl"
SOC_TB = ROOT / "hw" / "soc" / "tb"
SOC_FLOW = ROOT / "hw" / "soc" / "flow"
PILOT_RTL = ROOT / "hw" / "rtl"

NPU = (SOC_RTL / "soc_npu.v").read_text()
SER = (SOC_RTL / "soc_npu_ser.v").read_text()
BUS = (SOC_RTL / "soc_bus.v").read_text()
TOP = (SOC_RTL / "soc_top.v").read_text()


# ---------------------------------------------------------------------
# 1. The frozen directory is read and never written
# ---------------------------------------------------------------------
# docs/34-pilot-freeze.md section 2.1 pins every file in hw/rtl/ by git
# blob hash for the duration of the TTIHP26b shuttle. This work
# INSTANTIATES one of them rather than copying it, which is the whole
# argument of docs/51 section 3 -- and the argument is only worth
# anything if the file is still the frozen one.
PINNED = ("pilot_top.v", "lif_core.v", "aer_fifo.v", "scrub.v",
          "secded_enc.v", "secded_dec.v", "tmr_voter.v", "npu_regbank.v",
          "npu_regs.vh", "tt_um_melihakbulut_nssoc.v")


def _blob(path):
    out = subprocess.run(["git", "hash-object", str(path)],
                         capture_output=True, text=True, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_the_pilot_directory_is_unmodified_against_the_index():
    """Every pinned file matches what git has staged for it.

    A working-tree edit to hw/rtl/ is the one change this work is
    forbidden to make, and it is exactly the change that would be
    invisible in a passing simulation -- the SoC would pass against a
    pilot that is no longer the submission.
    """
    out = subprocess.run(["git", "status", "--porcelain", "--", "hw/rtl"],
                         capture_output=True, text=True, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    dirty = [ln for ln in out.stdout.splitlines() if ln.strip()]
    assert not dirty, (
        "hw/rtl/ has uncommitted changes, and docs/34 freezes it:\n"
        + "\n".join(dirty))
    for name in PINNED:
        assert (PILOT_RTL / name).is_file(), (
            "{} is missing from the frozen set".format(name))
        assert _blob(PILOT_RTL / name)


def test_the_soc_instantiates_the_frozen_pilot_and_does_not_copy_it():
    """soc_npu.v instantiates `pilot_top`, and no copy of it exists
    under hw/soc/.

    A copy would be the option docs/51 section 3 rejects: it diverges
    from the design being fabricated, and the divergence is silent.
    """
    assert re.search(r"\bpilot_top\s+#\(", NPU), \
        "soc_npu.v does not instantiate pilot_top"
    for p in (ROOT / "hw" / "soc").rglob("*.v"):
        if any(part in ("ext", "gen", "genp", "out", "tools", "pnr")
               for part in p.parts):
            continue
        assert not re.search(r"^\s*module\s+pilot_top\b", p.read_text(),
                             re.M), (
            "{} declares its own pilot_top".format(p))


def test_every_flow_that_builds_the_soc_reads_the_pilot_from_hw_rtl():
    """The sources come from the frozen directory, by path.

    A flow that had quietly started reading a copy would still build,
    still pass, and still be testing something other than the
    submission.
    """
    text = (SOC_FLOW / "sim_soc.sh").read_text()
    assert 'PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)' in text
    for name in ("pilot_top.v", "lif_core.v", "aer_fifo.v", "scrub.v"):
        assert '"$PILOT_RTL/{}"'.format(name) in text, (
            "hw/soc/flow/sim_soc.sh does not read {} from the frozen "
            "directory".format(name))


# ---------------------------------------------------------------------
# 2. One register map, one source
# ---------------------------------------------------------------------
def test_the_node_register_map_is_generated_and_not_written_down():
    """Every die-side offset soc_npu.v uses is a generated NAME.

    The module needs two of them, EVQ_IN and EVQ_OUT, and it reaches
    both through `ADDR_<NAME>` out of soc_npu_regs.vh. What is checked
    is that every `SA_` localparam -- this file's convention for a
    seven-bit serial word index, borrowed from pilot_top.v -- is
    DERIVED and not written down, and that the module declares no
    ADDR_ name of its own that could shadow a generated one.

    A numeric search would be the stronger check and is not available:
    the NPUCFG block has its own twelve-bit map in the same module, and
    its offsets collide numerically with the node's by construction.
    """
    assert '`include "soc_npu_regs.vh"' in NPU
    sa = re.findall(r"localparam\s*\[6:0\]\s+(SA_\w+)\s*=\s*([^;]+);", NPU)
    assert sa, "soc_npu.v declares no serial word-index constants"
    for name, expr in sa:
        assert re.fullmatch(r"\s*ADDR_\w+\[8:2\]\s*", expr), (
            "{} is written down as {!r} instead of derived from the "
            "generated header".format(name, expr.strip()))
        reg = name[len("SA_"):]
        assert reg in ADDR, (
            "{} names {}, which is not a register in "
            "regmap/regmap.yaml".format(name, reg))
    assert not re.search(r"localparam[^;]*\bADDR_\w+\s*=", NPU), (
        "soc_npu.v declares its own ADDR_ constant, shadowing the "
        "generated map")


def test_the_generated_soc_header_is_current_and_unguarded():
    """regmap/generate.py --check, plus the property that made the
    second output necessary.

    hw/rtl/npu_regs.vh keeps its include guard because exactly one
    module in that directory includes it. hw/soc/rtl/soc_npu_regs.vh
    must NOT have one: soc_npu.v and pilot_top.v are compiled together,
    and a guarded body include reaches the first module and hands every
    later one an empty file. docs/39 section 8 defect 1 is that failure
    happening once already.
    """
    out = subprocess.run([sys.executable, "regmap/generate.py", "--check"],
                         capture_output=True, text=True, cwd=str(ROOT))
    assert out.returncode == 0, out.stdout + out.stderr

    soc = (SOC_RTL / "soc_npu_regs.vh").read_text()
    assert "`ifndef" not in soc and "`define" not in soc, (
        "hw/soc/rtl/soc_npu_regs.vh has an include guard; a guarded body "
        "include blanks every module after the first")
    frozen = (PILOT_RTL / "npu_regs.vh").read_text()
    assert "`ifndef NPU_REGS_VH" in frozen

    # Same content, guard aside: one source, two consumers.
    strip = lambda t: [ln for ln in t.splitlines()          # noqa: E731
                       if ln.startswith("localparam")]
    assert strip(soc) == strip(frozen)


def test_the_program_reaches_the_node_map_through_generated_constants():
    """hw/soc/tb/sw/soc_npucfg.h describes the NPUCFG block and NOT the
    node.

    The node's map has a single source and a generated C header; the
    NPUCFG block's has never been described anywhere, which is the same
    split docs/40 section 8.1 states for the CLINT and the GPTIMER. A
    node offset written into the hand-maintained header would be a
    second copy of a generated map.
    """
    hdr = (SOC_TB / "sw" / "soc_npucfg.h").read_text()
    body = re.sub(r"/\*.*?\*/", "", hdr, flags=re.S)
    defined = set(re.findall(r"#define\s+(\w+)", body))
    for name in ADDR:
        assert "NPU_" + name not in defined, (
            "soc_npucfg.h defines NPU_{}, which is a NODE register and "
            "belongs to the generated npu_regs.h".format(name))
    # And the generator that produces the node map runs on every build,
    # so the program cannot be compiled against a stale copy of it.
    assert "gen_npu_vectors.py" in (SOC_FLOW / "build_sw_soc.sh").read_text()


# ---------------------------------------------------------------------
# 3. The map, the fabric and the top level agree
# ---------------------------------------------------------------------
def test_the_npu_region_has_a_fabric_port_and_the_fabric_decodes_it():
    """The frozen 256 MiB window is reached.

    docs/39 section 9 item 4 recorded it reaching the error slave. This
    is the check that it no longer does, stated over the generated map
    and the fabric's decode rather than over either alone.
    """
    assert PORTS.get("npu") == "NPU", (
        "regmap/memmap.yaml does not give the NPU region a fabric port")
    assert REGIONS["NPU"][4] == "implemented"
    assert "SOC_MASK_NPU) == SOC_BASE_NPU" in BUS, (
        "soc_bus.v does not decode the NPU region")
    assert "s_rdata_5_i" in BUS


def test_the_top_level_wires_the_npu_to_the_line_the_map_assigns():
    """The interrupt goes to the wire index the frozen map names.

    docs/40 assigned NPUCFG source 24 on fast local line 12 before this
    block existed. What is checked is that soc_top.v reaches that line
    through the GENERATED constant -- a literal 12 here would be a
    second copy of the assignment.
    """
    assert "irq_fast[SOC_IRQLINE_NPUCFG]" in TOP
    assert "SOC_APBSLOT_NPUCFG" in TOP
    assert APB_SLOTS["NPUCFG"][3] == "implemented"
    irq, line, _mcause, _vec = IRQ_SOURCES["NPUCFG"]
    assert (irq, line) == (24, 12)


def test_the_vector_table_has_a_stub_for_the_npus_line():
    """A line that is assigned and vectors to the spurious handler is a
    line nobody would notice was wrong.

    crt0.S's table is 32 entries and the NPU's id is 16 + its line.
    """
    crt0 = (SOC_TB / "sw" / "crt0.S").read_text()
    idx = 16 + IRQ_SOURCES["NPUCFG"][1]
    rows = [ln for ln in crt0.splitlines()
            if re.match(r"\s*j\s+vec_\w+\s*//\s*{}\b".format(idx), ln)]
    assert len(rows) == 1, (
        "no single vector-table row for interrupt id {}".format(idx))
    assert "vec_spurious" not in rows[0], (
        "interrupt id {} still vectors to the spurious handler".format(idx))
    assert re.search(r"vec_fast12:\s*li t0, {}\b".format(idx), crt0), (
        "the stub does not report id {}".format(idx))


def test_spending_the_npus_line_left_the_spares_alone():
    """Implementing NPUCFG consumes nothing that was spare.

    docs/40 section 3.3's decision to build no PLIC rests on there being
    headroom on Ibex's fifteen fast local lines. NPUCFG was one of the
    thirteen sources that document already assigned, so this work moves
    a slot from reserved to implemented and does not touch the count.
    """
    used = {v[1] for v in IRQ_SOURCES.values()}
    assert len(used) == 13
    assert sorted(set(range(15)) - used) == SPARE_FAST_LINES == [13, 14]


# ---------------------------------------------------------------------
# 4. Things the design says about itself
# ---------------------------------------------------------------------
def test_the_transport_default_is_the_documented_rate():
    """SER_HALF defaults to 2, which is host obligation H1 at its limit.

    A default that silently ran the die faster than pilot_top.v section
    2 permits would be a host that violates the contract it is written
    against, and it would work in simulation right up until it did not.
    """
    m = re.search(r"parameter\s+integer\s+HALF\s*=\s*(\d+)", SER)
    assert m and int(m.group(1)) == 2
    assert "ERROR_soc_npu_ser_HALF_below_2" in SER, (
        "soc_npu_ser.v has no elaboration guard against HALF < 2")
    m = re.search(r"parameter\s+integer\s+SER_HALF\s*=\s*(\d+)", NPU)
    assert m and int(m.group(1)) == 2
    assert ".SER_HALF  (2)" in TOP or ".SER_HALF(2)" in TOP


def test_the_output_ack_pin_is_tied_off_and_says_why():
    """AER_OUT_ACK is deliberately unused.

    The serial EVQ_OUT read is itself the pop, so a second pop path into
    the die's one-entry show-ahead register would be a second way to
    lose an event. This is a decision, not an omission, and a future
    change that connects it should have to delete a comment that says so.
    """
    assert re.search(r"\.aer_out_ack\s*\(\s*1'b0\s*\)", NPU)
    assert "second pop path" in NPU


def test_the_reserved_parts_of_the_window_are_not_silently_decoded():
    """The window decodes sixteen node slots and faults everything else.

    docs/08 section 3.1 sketched descriptor rings in this region and
    docs/51 does not build them. A window that answered the ring area
    with something would make "reserved" untrue in the one place a
    future reader would trust it.
    """
    assert "addr_i[27:16] == 12'd0" in NPU
    assert "addr_i[11:9] == 3'd0" in NPU
    assert "N_NODES" in NPU


@pytest.mark.parametrize("name", ["soc_npu.v", "soc_npu_ser.v"])
def test_the_new_rtl_is_verilog_2005_and_carries_a_timescale(name):
    """House style, and the reason is the simulator.

    Icarus is this project's simulator (docs/38) and the whole SoC is
    read as Verilog-2005. A SystemVerilog construct here would build
    under cocotb's -g2012 and fail the flow.
    """
    text = (SOC_RTL / name).read_text()
    assert text.startswith("//")
    assert "`timescale 1ns / 1ps" in text
    for banned in ("always_ff", "always_comb", "logic ", "typedef",
                   "package ", "interface "):
        assert banned not in text, (
            "{} uses SystemVerilog construct {!r}".format(name, banned))


# ---------------------------------------------------------------------
# 5. docs/55: the two bounds, the reports, and the protected word
# ---------------------------------------------------------------------
def _lp(text, name, where, env=None):
    """One `localparam integer <name> = <expression>;`, evaluated.

    The right-hand side is restricted to integer literals, the four
    arithmetic operators, parentheses and names the caller has already
    resolved into `env`. That is enough for every constant this file
    checks and it is deliberately not enough for anything else: an
    evaluator that could reach further would be a test that could be
    made to pass by writing something clever in the RTL.
    """
    m = re.search(r"localparam\s+integer\s+" + name + r"\s*=\s*([^;]+);",
                  text)
    assert m, "no `localparam integer {} = ...;` in {}".format(name, where)
    expr = m.group(1).strip()
    assert re.fullmatch(r"[0-9A-Za-z_+\-*/() ]+", expr), (
        "{} in {} is {!r}, which this test will not evaluate".format(
            name, where, expr))
    try:
        return int(eval(expr, {"__builtins__": {}}, dict(env or {})))
    except NameError as exc:
        raise AssertionError(
            "{} in {} refers to {}, which the test has not resolved: "
            "{!r}".format(name, where, exc, expr))


def test_the_two_bounds_are_derived_from_one_frame():
    """soc_npu.v sizes the node window's response bound from the
    transport's frame length, and Verilog-2005 gives an instantiating
    module no way to read a submodule's localparam. So the two numbers
    are restated -- and this is the check that the restatement is still
    true.

    docs/40 section 7.4 records what ONE literal bit position, written
    in two places, cost soc_wdog.v. The window's bound is worse than a
    bit position: if HALVES_FRAME grew in the transport and not here,
    the window would give up on a frame that was still legally in
    flight, and the symptom would be an intermittent bus error on a
    healthy part.
    """
    nbits = _lp(SER, "NBITS", "soc_npu_ser.v")
    assert nbits == 40, "the pilot's frame is 40 bits (pilot_top.v P2)"
    setup = _lp(SER, "HALVES_SETUP", "soc_npu_ser.v")
    shift = _lp(SER, "HALVES_SHIFT", "soc_npu_ser.v", {"NBITS": nbits})
    gap = _lp(SER, "HALVES_GAP", "soc_npu_ser.v")
    env = {"HALVES_SETUP": setup, "HALVES_SHIFT": shift, "HALVES_GAP": gap}
    ser_frame = _lp(SER, "HALVES_FRAME", "soc_npu_ser.v", env)
    ser_slack = _lp(SER, "HALVES_SLACK", "soc_npu_ser.v")
    npu_frame = _lp(NPU, "SER_HALVES_FRAME", "soc_npu.v")
    npu_slack = _lp(NPU, "SER_HALVES_SLACK", "soc_npu.v")
    assert (ser_frame, ser_slack) == (npu_frame, npu_slack), (
        "soc_npu.v thinks a serial frame is {} half periods plus {} of "
        "slack and soc_npu_ser.v says {} plus {}. The node window's "
        "bound is derived from the first pair and the transport's from "
        "the second, so they cannot disagree.".format(
            npu_frame, npu_slack, ser_frame, ser_slack))
    # And the transport's own arithmetic is the frame it actually
    # drives: setup + 2 x NBITS + gap, in half periods.
    assert shift == 2 * nbits
    assert ser_frame == setup + 2 * nbits + gap


def test_the_frame_bound_expires_on_greater_or_equal_and_not_on_equal():
    """An upset that pushes a guard counter ABOVE its bound must expire
    now, not wrap.

    With `==` the counter would count up, wrap through its whole range
    and only then reach the bound -- which is the unbounded stall the
    guards exist to remove, rebuilt inside the guard itself. Both
    counters are checked, because the two were written at different
    times and only one of them has a formal invariant behind it.
    """
    assert "guard >= GUARD_MAX[GUARD_W-1:0]" in SER, (
        "soc_npu_ser.v's frame bound no longer compares with >=")
    assert "win_guard >= WIN_MAX[WIN_GRD_W-1:0]" in NPU, (
        "soc_npu.v's window bound no longer compares with >=")


def test_a_bound_that_fires_fails_the_access_and_says_which_bound():
    """docs/52 section 12 item 1 asked for "a load access fault the
    program can handle" instead of a system reset, and for the part to
    say what happened.

    Half of that is the error response and half is the report. A bound
    that ended the wait and returned ZERO as data would be worse than
    the hang it replaced: the CPU would carry on with a register value
    that is not the register's.
    """
    assert "win_err_q <= win_err_q | ser_timeout;" in NPU, (
        "an aborted serial frame no longer fails the node-window access")
    assert re.search(r"end else if \(win_expire\) begin\s*\n(\s*//[^\n]*\n)*"
                     r"\s*win_err_q <= 1'b1;", NPU), (
        "an expired window wait no longer fails the access")
    assert "sticky_ev[C_SER_TO   - C_STICKY0] = ser_timeout;" in NPU
    assert ("sticky_ev[C_WIN_TO   - C_STICKY0] = win_expire || win_orphan;"
            in NPU), (
        "the window's two recoveries no longer share the cause bit that "
        "tells an operator the node window had to repair itself")


def test_the_window_bound_is_armed_by_the_grant_and_not_by_the_state():
    """The first version of this bound was armed by `win_state`, and it
    MISSED TWO OF THE SEVEN RECORDS IT WAS BUILT FOR.

    docs/55 section 8.2 is that measurement. The failure the state-armed
    version modelled is "the window waits for ever"; two of docs/52's
    seven dead machines are different shapes, and a counter that turns
    only in W_ISSUE and W_WAIT does not run in either:

      * the window FORGETS -- `win_state` W_WAIT to W_IDLE with a granted
        request unanswered. Nothing is waiting, so nothing counts.
      * the window is BUSY WITH NOTHING OWED -- W_IDLE to W_ISSUE. It
        issues a frame nobody asked for and raises rvalid with no grant
        behind it, which puts soc_bus.v's response-ownership queue out of
        step and sends every later response to the wrong master.

    Both are facts about the FABRIC HANDSHAKE rather than about this
    FSM's encoding, and both are answered from `win_out`: one bit that
    says the slave owes a response. This test exists to stop a future
    edit re-deriving the state-armed version, which reads more naturally
    and is wrong.
    """
    assert re.search(r"else if \(gnt_o\)\s+win_out <= 1'b1;", NPU), (
        "win_out is no longer set by the grant")
    assert re.search(r"else if \(rvalid_o\)\s+win_out <= 1'b0;", NPU), (
        "win_out is no longer cleared by the response")
    assert "wire win_expire = win_out &&" in NPU, (
        "the window's bound is armed by something other than an "
        "outstanding request; docs/55 section 8.2 measured what the "
        "state-armed version missed")
    assert "wire win_orphan = !win_out && (win_state != W_IDLE);" in NPU, (
        "the window no longer detects a state that no grant put it in")
    # And the orphan recovery must NOT answer the fabric.
    m = re.search(r"if \(win_orphan\) begin(.*?)end else if", NPU, re.S)
    assert m, "the orphan recovery is gone"
    assert "W_RESP" not in m.group(1), (
        "the orphan recovery returns a response. It must not: an rvalid "
        "the fabric was never expecting is the whole reason that record "
        "was fatal.")
    # And the transport itself must not present a partial frame as data.
    assert re.search(r"rdata_o\s*<= 32'd0;\s*\n\s*done_o\s*<= 1'b1;\s*\n"
                     r"\s*timeout_o\s*<= 1'b1;", SER), (
        "soc_npu_ser.v no longer zeroes rdata_o when it aborts a frame")


def test_the_protected_word_bundles_the_flags_it_cannot_triple_alone():
    """The replication bound, asserted rather than trusted.

    hw/rtl/pilot_top.v section 8.2 proves three replicas cannot be held
    apart over ONE bit, and nine of the eleven fields this bank protects
    are one bit wide. The answer is docs/41 section 4.2's: bundle them
    into one word and replicate the WORD. A future edit that gave any of
    them a bank of its own would produce a netlist with one flip-flop
    and a voter voting it against itself, and every test and every proof
    in this repository would still pass.

    soc_tmr_bank.v refuses below four bits, so the only thing this test
    has to check is that the bundle is still a bundle.
    """
    ncause = _lp(NPU, "NCAUSE", "soc_npu.v")
    nsticky = ncause - _lp(NPU, "C_INJ_OVF", "soc_npu.v")
    prot_w = 2 + nsticky + ncause
    assert prot_w >= 4, (
        "the protected word is {} bits and soc_tmr_bank refuses below "
        "four; below that the MIX transform is silently disarmed".format(
            prot_w))
    # Three banks, one voter, all at PROT_W.
    assert len(re.findall(r"soc_tmr_bank\s*#\(\.W\(PROT_W\)", NPU)) == 3
    assert "tmr_voter #(.WIDTH(PROT_W)) u_cfg_vote" in NPU
    # And the fields are inside it rather than beside it.
    for field in ("P_IN_EN", "P_OUT_EN", "P_STICKY", "P_MASK"):
        assert field in NPU, (
            "{} is no longer a named field of the protected "
            "word".format(field))


def test_the_report_is_inside_the_protected_word():
    """docs/16 section 5.8 measured this repository's own safety-net
    report being a single point of failure: an upset could erase the
    announcement of the very event it caused, and docs/16 section 5.9 is
    the fix at minus two flip-flops.

    So the cause bank's own mismatch report is a FIELD of the bank. The
    write that repairs the replica and the write that records the repair
    are the same write on the same edge, which is docs/30 section 4.2's
    rule and docs/41 section 5.3's application of it.
    """
    c_cfg_tmr = _lp(NPU, "C_CFG_TMR", "soc_npu.v")
    c_sticky0 = _lp(NPU, "C_INJ_OVF", "soc_npu.v")
    assert c_cfg_tmr >= c_sticky0, (
        "C_CFG_TMR is below the first sticky bit, so it is not carried "
        "in the protected word's sticky field at all")
    assert "sticky_ev[C_CFG_TMR  - C_STICKY0] = prot_mismatch;" in NPU


def test_nothing_instantiates_the_npu_unhardened():
    """HARDEN = 0 exists so the redundancy can be PRICED against the
    same file list with the same recipe -- docs/41 section 6.5 -- and
    for nothing else. A design that shipped it would have the cause
    register docs/52 measured producing a false fault report in 16 of
    100 draws.
    """
    m = re.search(r"parameter\s+integer\s+HARDEN\s*=\s*(\d+)", NPU)
    assert m and int(m.group(1)) == 1, (
        "soc_npu.v's HARDEN no longer defaults to 1")
    assert ".HARDEN" not in TOP, (
        "soc_top.v overrides soc_npu's HARDEN; the only configuration "
        "this SoC ships is the hardened one")


def test_the_queue_storage_is_left_alone_on_purpose():
    """The measurement disagreeing with instinct, written into a test.

    `evq_data` is 41.2 % of the connection's flip-flops and 53.5 % of
    its area, and docs/52 measured it producing ZERO silent wrong
    inferences in 100 draws -- because the queues hold a couple of live
    entries out of eight, so most of those bits are storage nothing will
    read. A hardening wave that started with the biggest structure would
    have spent its whole budget there.

    There is no way to test for the ABSENCE of a future protection, so
    this tests for the presence of the argument: soc_npu.v has to keep
    saying why, and hw/rtl/aer_fifo.v has to stay the only thing
    protecting those entries.
    """
    assert "NOTHING IN THIS FILE PROTECTS" in NPU and "QUEUE STORAGE" in NPU, (
        "soc_npu.v no longer records that the queue storage is "
        "deliberately unprotected; if that changed, it changed against "
        "docs/52's measurement and needs a measurement of its own")
    # The queues are still hw/rtl/aer_fifo.v and still at 16 x 8.
    assert len(re.findall(r"aer_fifo #\(\.WIDTH \(16\)", NPU)) == 2
