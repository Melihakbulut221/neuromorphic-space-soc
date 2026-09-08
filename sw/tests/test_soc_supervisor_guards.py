# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Guards on the second fault-injection workload, the static
partitioned supervisor of `docs/46`.

WHY THIS FILE EXISTS

`docs/46`'s whole result rests on two properties of
`hw/soc/tb/sw/fi_supervisor.c` that nothing else in this repository
checks, and both of them are properties a later edit could destroy
without failing anything:

**1. The program kicks the watchdog from exactly one place inside its
schedule.** Every number in `docs/46` -- the kick-interval ratio, the
admissible `WINS`, the campaign's escalation counts -- is a measurement
of one kick placement, argued at length in the source file's "WHERE THE
KICK GOES" section. A second kick added anywhere in the frame loop would
change the cadence and silently invalidate the document, and it would do
so while every simulation still passed, because a program that kicks
more often is a program the watchdog is happier with.

**2. The second startup file has not drifted on the things that
matter.** `hw/soc/tb/sw/sup_crt0.S` is a copy of a file this repository
kept single precisely so it could not drift, and its own header says so.
What stops the copy being dangerous is that the two Ibex constraints
which cost `docs/38` a debugging session each -- section 7.5 defect 3,
`mtvec` is 256-byte aligned and vectored-only, and defect 4, the reset
vector is fixed -- are enforced by the LINKER SCRIPT, which is shared.
These tests assert that the supervisor is still built against that
shared script and not against a copy of it.

WHAT THIS FILE DOES **NOT** COVER, because a green check is only as wide
as the thing it examined and `docs/41` section 6.6 lists nine times this
repository has been bitten by that:

  * It reads SOURCE TEXT. It does not run the program, does not
    disassemble it and cannot see a kick reached through a function
    pointer or a macro it does not know about. It is a guard against
    the ordinary edit, not against a determined one.
  * It says nothing about whether the kick placement is RIGHT. That is
    an argument, it is in the source file, and `docs/46` section 4 is
    where it is defended.
  * It says nothing about the measured cadence. A build with different
    partitions would have a different one and this file would stay
    green; the cadence is measured by the campaign's own control 2,
    which prints it on every run.
  * It does not check the assembly. `sup_crt0.S`'s privilege switch is
    exercised by running the program -- a supervisor whose `ecall` path
    were wrong would not complete a single frame -- and not here.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_soc_supervisor_guards.py
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SW = ROOT / "hw" / "soc" / "tb" / "sw"
FLOW = ROOT / "hw" / "soc" / "flow"

SUP_C = SW / "fi_supervisor.c"
SUP_S = SW / "sup_crt0.S"
SUP_H = SW / "sup_config.h"
BUILD = FLOW / "build_sw_sup.sh"
FI_CORE = FLOW / "fi_core.sh"


def _text(p):
    return p.read_text(encoding="utf-8")


def _code_lines(p):
    """Source lines with // and /* */ comment bodies removed.

    Every guard below is about what the program DOES, and this file's
    sources carry more comment than code -- a naive substring count
    would be dominated by prose that mentions the very thing being
    counted.
    """
    text = _text(p)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out = []
    for line in text.splitlines():
        line = re.sub(r"//.*$", "", line)
        if line.strip():
            out.append(line)
    return out


# =====================================================================
# 1. The kick
# =====================================================================
def test_the_supervisor_kicks_from_exactly_two_places():
    """One arming kick on entering the operational phase, one per frame.

    Two and not one: `docs/43` section 4.6 found by running it that a
    cadence contract armed before a kick makes the very next kick early,
    so the program has to kick before it declares the contract. Two and
    not three: a third kick anywhere would change the cadence every
    number in `docs/46` is measured from.
    """
    calls = [ln for ln in _code_lines(SUP_C) if "wdog_kick()" in ln]
    assert len(calls) == 2, (
        "expected exactly two calls to wdog_kick(), found %d:\n%s"
        % (len(calls), "\n".join(calls)))


def test_only_the_supervisor_can_reach_the_watchdog():
    """No partition writes a watchdog register.

    This is the property PMP buys and it is what makes a one-kick-per
    -frame cadence meaningful at all: if a partition could kick, the
    cadence would be the union of five programs' cadences. The check is
    textual and weak; the enforcement is `pmp_init`, which does not give
    U-mode the peripheral bus at all.
    """
    text = _text(SUP_C)
    body = text[text.index("// The partitions."):text.index("static void (*const task_entry")]
    for token in ("WDOG_", "wdog_kick", "SOC_APB_BASE", "SOC_TIMER0_BASE"):
        assert token not in body, (
            "a partition names %s; partitions must touch nothing but "
            "their own mailbox, the shared message and their own stack"
            % token)


def test_the_kick_is_the_last_thing_in_the_frame():
    """The frame's kick follows the partition loop, not the tick.

    `docs/46` section 4 rejects kicking from the tick handler because a
    system whose partitions have all deadlocked still takes its timer
    interrupt. That rejection is only worth anything if the tick handler
    does not, in fact, kick.
    """
    assert "wdog_kick" not in _text(SUP_S), (
        "sup_crt0.S kicks the watchdog. The tick handler must not: see "
        "placement (a) in fi_supervisor.c's WHERE THE KICK GOES.")


def test_the_cadence_bounds_are_build_errors_and_have_no_default():
    """Both of `docs/43` section 4.2's bounds, checked at compile time.

    A build that gets either wrong does not fail; it escalates in a
    loop, which is the brick `docs/40` section 7.2 spent a section on.
    The load-bearing part is that neither bound has a DEFAULT: a default
    would be a number for one dispatch discipline at one frame period,
    silently wrong for the other, and the first version of this file had
    exactly that -- `SUP_KICK_MAX` defaulted to zero and the check was
    skipped in every build that did not pass it.
    """
    src = _text(SUP_C)
    assert "#if defined(SUP_WINDOWED) && !defined(SUP_SWEEP)" in src
    assert src.count("#error") >= 3, (
        "expected a build error for a missing cadence, for a timeout "
        "below i_max and for a window that opens after i_min")
    for name in ("SUP_KICK_MIN", "SUP_KICK_MAX"):
        assert not re.search(r"^#define %s\b" % name, src, re.M), (
            "%s has a default; a guard that is inert unless somebody "
            "remembers to arm it is a guard that reads wider than it is"
            % name)


# =====================================================================
# 2. The second startup file
# =====================================================================
def test_the_supervisor_is_linked_with_the_shared_linker_script():
    """`link_soc.ld`, not a copy of it.

    The script is what asserts `_start` onto Ibex's reset vector and the
    vector table onto a 256-byte boundary at exactly 128 bytes. A copy
    would be a second place for `docs/38` section 7.5 defects 3 and 4 to
    happen.
    """
    build = _text(BUILD)
    assert '-T "$SW/link_soc.ld"' in build
    assert not list(SW.glob("link_sup*.ld")), (
        "a supervisor-specific linker script has appeared; the "
        "constraints it would carry are already asserted in link_soc.ld")


def test_the_linker_script_still_asserts_both_ibex_constraints():
    """The guard the copied startup file relies on."""
    ld = _text(SW / "link_soc.ld")
    assert "_start == __soc_reset_vector" in ld
    assert "(trap_vectors & 0xff) == 0" in ld
    assert "trap_vectors_end - trap_vectors == 128" in ld


def test_the_two_workloads_use_different_startup_files_and_only_that():
    """`docs/42`'s workload is untouched by this work.

    `docs/43` section 9.1 rests on `fi_workload.c` producing a
    byte-identical ROM image to `docs/42`'s. That survives only if
    nothing in the supervisor's build path reaches into it.
    """
    fi = [ln for ln in _text(FLOW / "build_sw_fi.sh").splitlines()
          if not ln.lstrip().startswith("#")]
    sup = [ln for ln in _text(BUILD).splitlines()
           if not ln.lstrip().startswith("#")]
    assert any('"$SW/crt0.S" "$SW/fi_workload.c"' in ln for ln in fi)
    assert any('"$SW/sup_crt0.S" "$SW/fi_supervisor.c"' in ln for ln in sup)
    assert not [ln for ln in fi if "sup_crt0" in ln or "fi_supervisor" in ln]
    assert not [ln for ln in sup
                if "crt0.S" in ln.replace("sup_crt0.S", "")
                or "fi_workload" in ln]


def test_the_supervisor_vector_table_has_thirty_two_entries():
    """Ibex vectors interrupts at BASE + 4*cause and has no direct mode.

    The linker asserts the table's SIZE. This asserts its SHAPE, which
    the linker cannot see: 32 `j` instructions between the two labels
    and nothing else, so a table that reached 128 bytes by some other
    means would still fail.
    """
    text = _text(SUP_S)
    body = text[text.index("trap_vectors:"):text.index("trap_vectors_end:")]
    jumps = [ln for ln in body.splitlines() if re.match(r"\s*j\s+\w", ln)]
    assert len(jumps) == 32, "found %d vector entries, expected 32" % len(jumps)
    assert ".option norvc" in text[:text.index("trap_vectors:")][-400:], (
        "the vector table is not inside a norvc region; one entry "
        "assembled compressed would put every later vector at the "
        "wrong offset")


# =====================================================================
# 3. The isolation the cadence argument depends on
# =====================================================================
def test_the_partition_region_is_a_legal_napot_block():
    """A NAPOT region whose base is not naturally aligned does not
    encode a slightly wrong region, it encodes a much larger one -- and
    a partition that could reach its neighbour's memory would make the
    isolation claim false without failing anything.

    The size is checked to be a power of two of at least eight bytes,
    which is what the encoding requires, and the C is checked to align
    the array to it.
    """
    m = re.search(r"#define SUP_TASK_MEM (\d+)", _text(SUP_H))
    assert m, "SUP_TASK_MEM is not defined in sup_config.h"
    size = int(m.group(1))
    assert size >= 8 and (size & (size - 1)) == 0, (
        "SUP_TASK_MEM = %d is not a power of two of at least 8 and "
        "cannot be described in NAPOT form" % size)
    assert "__attribute__((aligned(SUP_TASK_MEM)))" in _text(SUP_C)
    assert "__attribute__((aligned(64)))" in _text(SUP_C), (
        "the shared message buffer must be naturally aligned to its "
        "64-byte NAPOT region")


def test_the_napot_encoding_is_the_one_the_specification_defines():
    """`napot(base, size)` re-derived independently.

    The expression in the C is `(base >> 2) | ((size >> 3) - 1)`. This
    rebuilds the region it describes from the encoding's definition --
    the address field is the block's base with the low log2(size)-3 bits
    set -- and checks the two constants the program actually uses.
    """
    src = _text(SUP_C)
    assert "return (base >> 2) | ((size >> 3) - 1u);" in src

    def napot(base, size):
        return (base >> 2) | ((size >> 3) - 1)

    def decode(v):
        ones = 0
        while v & 1:
            ones += 1
            v >>= 1
        return (v << (ones + 2), 1 << (ones + 3))

    for base, size in ((0xC0000000, 0x2000), (0x00000800, 1024), (0x400, 64)):
        assert decode(napot(base, size)) == (base, size)


def test_the_partitions_run_in_user_mode():
    """The isolation mechanism `docs/09` part B track 3 chose.

    `sup_dispatch` must clear mstatus.MPP before its mret, or every
    partition would run in M-mode with PMP not applying to it and the
    whole arrangement would be a function call with extra steps.
    """
    text = _text(SUP_S)
    switch = text[text.index("sup_dispatch:"):text.index("sup_dispatch_ret:")]
    assert "csrc  mstatus, t0" in switch and "0x1800" in switch, (
        "sup_dispatch does not clear mstatus.MPP; the partition would "
        "run in M-mode")
    assert "mret" in switch


# =====================================================================
# 4. The flow
# =====================================================================
def test_fi_core_can_build_both_workloads():
    """One instrument, two programs.

    `docs/46`'s comparison against `docs/42` and `docs/43` is only worth
    anything because the testbench, the site table and the classifier
    are identical for both. That holds as long as the only thing
    `FI_WORKLOAD` changes is which source file is compiled.
    """
    core = _text(FI_CORE)
    assert "FI_WORKLOAD" in core
    assert "build_sw_fi.sh" in core and "build_sw_sup.sh" in core
    assert BUILD.exists() and (FLOW / "build_sw_fi.sh").exists()


def test_the_tick_period_and_the_partition_count_are_defined_once():
    """`sup_crt0.S` reprograms mtimecmp and `fi_supervisor.c` schedules
    against the same period. A second copy of either number would be a
    defect waiting for a build that changed one of them."""
    assert '#include "sup_config.h"' in _text(SUP_S)
    assert '#include "sup_config.h"' in _text(SUP_C)
    for name in ("SUP_TICK_PERIOD", "SUP_NTASK", "SUP_TASK_MEM", "SUP_FRAMES"):
        defs = re.findall(r"^#define %s\b" % name, _text(SUP_H), re.M)
        assert len(defs) == 1, "%s is defined %d times" % (name, len(defs))
        for other in (SUP_C, SUP_S):
            assert not re.search(r"^#define %s\b" % name, _text(other), re.M), (
                "%s is redefined in %s" % (name, other.name))
