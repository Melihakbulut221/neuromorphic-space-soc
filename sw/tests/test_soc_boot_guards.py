"""Guards on the boot flow: what the RTL, the flows and the loader must
keep true, checked textually because no simulation reaches them.

WHY THIS FILE EXISTS

`docs/68` builds a boot flow out of four things that are each somebody
else's block -- the QSPI reads of `docs/66`, the memory codec of
`docs/67`, the watchdog of `docs/40`, and one new register block -- and
the properties that hold it together are properties of the WIRING and of
the ORDER, which is exactly what a block-level suite and a proof cannot
see:

  * `hw/soc/formal/soc_boot.sby` proves that the boot counter is not
    writable. It says nothing about `rst_ni` on that block being the
    SYSTEM reset, which is what makes the counter count boots.
  * `hw/soc/tb/cocotb/test_soc_boot.py` drives the block's ports by
    hand. It says nothing about the ports being connected.
  * The whole-SoC run boots. It says nothing about the RAM sweep being
    first, because on a healthy simulation without `+ram_random` an
    unswept RAM is indistinguishable from a swept one -- which is
    precisely the trap this document exists to avoid falling into.

The rule these follow is the one `feedback-guard-placement` states and
`docs/40` section 7.2 learned the hard way: a guard belongs at the stage
that can satisfy it. The sweep's correctness is a property of the ORDER
of instructions in `boot_crt0.S`, so it is checked there; the counter's
authority is a property of the RTL, so it is checked there; the
attempt limit's relationship to the watchdog's escalation is a property
of two parameters in `soc_top.v`, so it is checked there.

WHAT THIS FILE DOES **NOT** COVER

  * Whether the loader WORKS. `hw/soc/flow/sim_soc.sh` is that, and
    `docs/68` sections 5 to 8 are its measurements.
  * Whether the sweep is sufficient in silicon. It is sufficient against
    `soc_mem.v`'s model of an SRAM; no macro has been simulated
    (`docs/12` section 8 stands).
  * Anything about area, timing or placement.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_soc_boot_guards.py
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOC_RTL = ROOT / "hw" / "soc" / "rtl"
SOC_FLOW = ROOT / "hw" / "soc" / "flow"
SOC_SW = ROOT / "hw" / "soc" / "tb" / "sw"
SOC_TB = ROOT / "hw" / "soc" / "tb"


def _strip_comments(text):
    out = []
    for line in text.splitlines():
        s = line.split("//", 1)[0]
        out.append(s)
    return "\n".join(out)


# ----------------------------------------------------------------------
# 1. The block, and the reset domains that give it its meaning
# ----------------------------------------------------------------------


def test_the_boot_block_is_entirely_in_the_power_on_domain():
    """Every flip-flop in `soc_boot.v` is reset by `rst_por_ni` and none
    by `rst_ni`.

    That is what "survives the reset it describes" means, and it is the
    property `docs/41` section 3.1 established for the watchdog's
    record. The system reset is an INPUT to the logic here -- its
    release is what the boot counter counts -- so a file that used it as
    a reset would both erase the record and count nothing.
    """
    src = _strip_comments((SOC_RTL / "soc_boot.v").read_text())
    sensitivities = re.findall(r"always @\(posedge clk_i([^)]*)\)", src)
    assert sensitivities, "no clocked block found in soc_boot.v"
    for s in sensitivities:
        assert "rst_ni" not in s.replace("rst_por_ni", ""), (
            "a clocked block in soc_boot.v is reset by the system reset; "
            "everything in that block must be in the power-on domain")
        assert "negedge rst_por_ni" in s, (
            "a clocked block in soc_boot.v has no power-on reset")


def test_soc_top_gives_the_boot_block_both_resets_the_right_way_round():
    """`rst_ni` on the instance is the SYSTEM reset and `rst_por_ni` the
    power-on one. Swapping them would give a counter that resets on
    every watchdog reset -- a boot counter that cannot count boots --
    and a report erased by the reset it describes."""
    top = _strip_comments((SOC_RTL / "soc_top.v").read_text())
    m = re.search(r"soc_boot\s*#\(.*?\)\s*u_boot\s*\((.*?)\n  \);", top,
                  re.S)
    assert m, "soc_top.v no longer instantiates soc_boot as u_boot"
    inst = m.group(1)
    assert re.search(r"\.rst_ni\s*\(\s*rst_sys_n\s*\)", inst), (
        "u_boot's rst_ni is not rst_sys_n: the boot counter would not "
        "count boots")
    assert re.search(r"\.rst_por_ni\s*\(\s*rst_ni\s*\)", inst), (
        "u_boot's rst_por_ni is not the power-on reset: the boot report "
        "would not survive the reset it describes")


def test_the_boot_block_drives_nothing_but_its_own_read_data():
    """THE STRUCTURAL FORM OF `docs/40` SECTION 7.2's FIX.

    That document's brick loop was a register outside the reset domain
    that could shorten the next boot's budget. Here nothing outside the
    reset domain can reach a budget at all, because the block has no
    output except the APB read path -- and this test is what keeps that
    true when somebody adds a field to it.
    """
    src = _strip_comments((SOC_RTL / "soc_boot.v").read_text())
    ports = src.split("#(", 1)[1].split(") (", 1)[1].split(");", 1)[0]
    outputs = re.findall(r"output\s+(?:reg|wire)?\s*(?:\[[^\]]*\]\s*)?(\w+)",
                         ports)
    assert set(outputs) == {"prdata_o", "pready_o", "pslverr_o"}, (
        "soc_boot.v has grown an output beyond the APB read path: {}. "
        "Anything this block drives is state that survives a reset and "
        "then influences the machine after it, which is exactly the "
        "shape docs/40 section 7.2 bricked on".format(sorted(outputs)))


def test_the_attempt_limit_is_a_parameter_and_no_register_reaches_it():
    """`soc_wdog.v` W2's argument, one level up: a bound enforced by a
    parameter cannot be misconfigured; one enforced by a writable
    register can. LIMIT appears in the read decode and nowhere in a
    write."""
    src = _strip_comments((SOC_RTL / "soc_boot.v").read_text())
    assert re.search(r"parameter\s+integer\s+LIMIT\s*=", src)
    for line in src.splitlines():
        if "LIMIT" in line and "pwdata_i" in line:
            raise AssertionError(
                "a write reaches the attempt limit in soc_boot.v: " + line)


def test_the_attempt_limit_and_the_watchdogs_escalation_agree():
    """The whole of `docs/68` section 6's timing argument, as a check.

    The loader's last attempt must be a boot during which the watchdog
    has ALREADY asserted its external pin -- software gives up after the
    hardware has told the platform, never before. The watchdog asserts
    on its WDOG_ESCALATE-th stage-2 reset, which begins boot number
    WDOG_ESCALATE; the loader's last attempt is boot BOOT_LIMIT - 1. So
    BOOT_LIMIT - 1 >= WDOG_ESCALATE.
    """
    top = _strip_comments((SOC_RTL / "soc_top.v").read_text())
    limit = re.search(r"parameter\s+integer\s+BOOT_LIMIT\s*=\s*(\d+)", top)
    esc = re.search(r"\.WDOG_ESCALATE\s*\(\s*(\d+)\s*\)", top)
    assert limit and esc, "BOOT_LIMIT or WDOG_ESCALATE has moved in soc_top.v"
    limit, esc = int(limit.group(1)), int(esc.group(1))
    assert limit - 1 >= esc, (
        "BOOT_LIMIT = {} and WDOG_ESCALATE = {}: the loader gives up on "
        "boot {} but the watchdog does not assert its external pin until "
        "boot {}, so software would give up before the platform has been "
        "told".format(limit, esc, limit - 1, esc))


# ----------------------------------------------------------------------
# 2. The sweep
# ----------------------------------------------------------------------


def test_the_ram_sweep_is_the_first_thing_that_touches_the_ram():
    """`docs/67`'s check bits and an SRAM that powers up undefined:
    every word of the RAM has to be WRITTEN before any of it is read.
    Nothing in a passing simulation shows this -- `soc_mem.v`'s model
    comes up as valid all-zero codewords unless `+ram_random` is given
    -- so the order is checked here, in the file that has it."""
    src = (SOC_SW / "boot_crt0.S").read_text()
    body = src.split("_start:", 1)[1]
    sweep = body.index("SOC_RAM_BASE")
    for later in ("la    sp,", "la    gp,", "__data_load", "call  boot_main"):
        assert body.index(later) > sweep, (
            "{!r} comes before the RAM sweep in boot_crt0.S. The loader's "
            "stack, its .data and its .bss are all in the RAM the sweep "
            "is initialising".format(later))


def test_the_sweep_writes_whole_words_in_the_shipped_build():
    """A byte store initialises ONE of a row's four byte codewords and
    leaves three as the SRAM powered up, so the first 32-bit load of
    that word is an uncorrectable. `sw` is the design; `sb` is the
    -DBOOT_SWEEP_BYTE counterfactual and it must be reachable only
    through that define."""
    src = (SOC_SW / "boot_crt0.S").read_text()
    body = src.split("_start:", 1)[1].split(".option rvc", 1)[0]
    assert "sw    zero, 0(t0)" in body, (
        "the shipped sweep no longer writes words")
    if "sb    zero, 0(t0)" in body:
        byte_at = body.index("sb    zero, 0(t0)")
        guard = body.rindex("#elif defined(BOOT_SWEEP_BYTE)", 0, byte_at)
        assert guard >= 0, (
            "boot_crt0.S has a byte sweep outside the BOOT_SWEEP_BYTE "
            "counterfactual")
    assert "#if defined(BOOT_NO_SWEEP)" in body, (
        "the no-sweep counterfactual has gone; docs/68 section 4's "
        "evidence that the sweep is load-bearing goes with it")


def test_the_sweep_covers_the_whole_region_the_map_declares():
    """Its bounds come from the generated header and not from a
    literal, so moving the RAM in `regmap/memmap.yaml` moves the
    sweep."""
    src = (SOC_SW / "boot_crt0.S").read_text()
    assert "SOC_RAM_BASE + SOC_RAM_SIZE" in src
    assert not re.search(r"li\s+t1,\s*0x[0-9A-Fa-f]+", src), (
        "boot_crt0.S has an address literal where the generated map "
        "should be")


# ----------------------------------------------------------------------
# 3. The loader
# ----------------------------------------------------------------------


def test_the_loader_verifies_the_ram_and_not_the_flash():
    """The checksum is computed from what came BACK OUT OF THE RAM. A
    loader that summed what the controller delivered would check the
    flash read and not the image, and an uncorrectable in a row it had
    just written would be the application's first mysterious fault
    instead of a reported boot failure."""
    src = (SOC_SW / "boot.c").read_text()
    m = re.search(r"for \(uint32_t w = 0; w < nwords; w\+\+\) \{\s*\n"
                  r"\s*sum \+= dst\[w\];", src)
    assert m, ("boot.c no longer sums the image out of the RAM; if the sum "
               "moved into the copy loop it is summing the flash read")


def test_the_loader_kicks_the_watchdog_only_on_progress():
    """`docs/40` section 5.4 refuses a stage-1 handler that kicks,
    because it would "let a program that does nothing else keep the
    watchdog satisfied from inside its own failure". The same rule
    applies to the copy: the kick is inside the loop that moves words,
    gated on the word index, so a loop that is not moving words does not
    kick."""
    src = (SOC_SW / "boot.c").read_text()
    kicks = re.findall(r"^\s*(.*wdog_kick\(\);.*)$", src, re.M)
    assert kicks, "boot.c no longer kicks the watchdog at all"
    gated = [k for k in kicks if "BOOT_KICK_WORDS" in k]
    assert len(gated) >= 2, (
        "the copy and the verify loops must each kick on the word index; "
        "found {}".format(kicks))
    assert "for (;;) { }" in src.split("boot_give_up", 1)[1], (
        "the give-up path no longer ends in a spin without a kick, which "
        "is the whole escalation")


def test_the_give_up_path_shortens_the_watchdog_and_stops_kicking():
    """And it may do that only because a stage-2 reset restores the
    reload to the maximum -- `docs/40` section 7.2's fix. This test
    checks the two halves are still both there: the shortening here, and
    the restore in `soc_wdog.v`."""
    src = (SOC_SW / "boot.c").read_text()
    give = src.split("static void boot_give_up", 1)[1].split("\n}", 1)[0]
    assert "WDOG_RLD" in give and "GPT_LD" in give, (
        "the give-up path no longer shortens the watchdog")
    assert "wdog_kick" not in give.split("BOOT_GIVEUP_RELOAD", 1)[1], (
        "the give-up path kicks the watchdog after shortening it, which "
        "is a loader that never gives up")
    wdog = _strip_comments((SOC_RTL / "soc_wdog.v").read_text())
    assert re.search(r"if \(stage2\)\s*reload <= \{WIDTH\{1'b1\}\};", wdog), (
        "soc_wdog.v no longer restores the reload to the maximum on a "
        "stage-2 reset; docs/40 section 7.2's brick returns and the "
        "loader's give-up path becomes a permanent short timeout")


def test_the_loader_checks_the_geometry_before_it_copies():
    """`load` and `bytes` come out of a flash the loader has not yet
    decided it can trust, and they are about to be used as a
    destination. The check must be BEFORE the copy and it must bound the
    image below the loader's own private RAM."""
    src = (SOC_SW / "boot.c").read_text()
    body = src.split("static int try_image", 1)[1]
    geom = body.index("geom_ok")
    copy = body.index("dst[w] = rd(QSPI_RX)")
    assert geom < copy, "boot.c copies before it checks the geometry"
    assert "__boot_private" in body[:copy], (
        "the geometry check does not bound the image below the loader's "
        "own stack")


def test_the_report_is_written_before_the_jump():
    """After the jump the loader does not run again, and a report
    written by the application would be the application's opinion of its
    own boot."""
    src = (SOC_SW / "boot.c").read_text()
    body = src.split("uint32_t boot_main", 1)[1]
    rpt = body.rindex("wr(BOOT_BRPT,")
    ret = body.rindex("return entry;")
    assert rpt < ret, "boot.c returns the entry point before it reports"


# ----------------------------------------------------------------------
# 4. The flows, and the model of a power-up
# ----------------------------------------------------------------------


def test_every_flow_that_builds_soc_top_reads_the_boot_block():
    """The defect `docs/57` and `docs/59` found: a module `soc_top.v`
    instantiates that some flow cannot resolve. `test_soc_synthesis_
    guards.py` checks this generically; this is the specific case, kept
    because a boot block missing from the fault-injection flow would
    silently drop the block from every campaign."""
    for name in ("sim_soc.sh", "syn_soc_top.sh", "pnr_soc_top.sh",
                 "fi_core.sh", "fi_npu.sh"):
        text = (SOC_FLOW / name).read_text()
        assert re.search(r"\bsoc_boot\b", text), (
            "hw/soc/flow/{} does not read soc_boot".format(name))


def test_the_power_up_model_is_on_by_default():
    """`SOC_RAM_RANDOM` defaults to 1. Without it `soc_mem.v`'s model
    comes up as valid all-zero codewords -- a memory that is already
    initialised -- and the loader's sweep proves nothing. A default of 0
    would make every run in `docs/68` vacuous."""
    text = (SOC_FLOW / "sim_soc.sh").read_text()
    assert re.search(r"SOC_RAM_RANDOM=\$\{SOC_RAM_RANDOM:-1\}", text), (
        "flow/sim_soc.sh no longer models a power-up by default")
    assert "+ram_random=" in text


def test_the_power_up_model_reaches_the_check_field():
    """Randomising the data and leaving the check field valid would be a
    memory that is still initialised, one level down. The testbench
    writes both, and the block that does it is behind a define that
    follows SOC_MEM_HARDEN because the check array does not exist when
    the codec is off."""
    tb = (SOC_TB / "tb_soc.v").read_text()
    assert "dut.u_ram.g_ecc.chk[ram_i]" in tb, (
        "tb_soc.v's power-up model no longer writes the check field")
    assert "`ifdef RAM_POWERUP_ECC" in tb
    flow = (SOC_FLOW / "sim_soc.sh").read_text()
    assert "RAM_POWERUP_ECC" in flow


def test_the_loader_and_the_application_are_linked_to_different_memories():
    """The ROM holds a loader and the program runs from RAM. A build in
    which both were linked to the ROM is the pre-`docs/68` arrangement
    and would silently reintroduce `docs/66` section 7.1's finding."""
    boot = (SOC_SW / "link_boot.ld").read_text()
    app = (SOC_SW / "link_app.ld").read_text()
    assert "*(.text .text.*)\n  } > rom" in boot, (
        "the loader's .text is no longer in the ROM")
    assert "*(.text .text.*)\n  } > ram" in app, (
        "the application's .text is no longer in the RAM")
    assert "__soc_reset_vector" in boot and "__soc_ram_base" in app
    build = (SOC_FLOW / "build_sw_soc.sh").read_text()
    assert "link_app.ld" in build and "link_boot.ld" in build
    assert "gen_boot_image.py" in build


def test_the_image_header_is_declared_once():
    """`hw/soc/tb/sw/soc_boot.h` is the contract between the generator
    and the loader. A second copy of the field order in either would be
    the defect `docs/44` section 5.4 refused for a parity matrix."""
    gen = (SOC_FLOW / "gen_boot_image.py").read_text()
    hdr = (SOC_SW / "soc_boot.h").read_text()
    assert "0x3142534E" in gen and "0x3142534Eu" in hdr, (
        "the image magic has moved in one of the two files")
    # The generator writes the header positionally and the loader reads
    # it by name; what must not happen is a second set of NAMES.
    assert "BOOT_IMG_W_" not in gen, (
        "gen_boot_image.py has grown its own copy of the field names")
    assert "soc_boot.h" in gen, (
        "gen_boot_image.py no longer names the header it is a contract "
        "with")
