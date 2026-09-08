# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Register map consistency tests (single-source discipline).

The YAML source (regmap/regmap.yaml) must stay in sync with both the
generated files and the normative register list in docs/10-npu-mvp-spec.md
section 10 ("must not diverge once the regmap flow is instantiated").

The same rule applies to hand-written bit masks anywhere else in the tree
that restate a position the YAML already fixes. sw/golden/secded.py
carries the FAULT_CLR_* and STATUS_DED_SEEN constants as literals, so
they are cross-checked against the generated field table at the end of
this file; nothing else in the golden models is allowed to re-type a bit
position without a check here.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sw"))


def test_generated_files_in_sync():
    """The committed generated files must match the YAML source exactly."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "regmap" / "generate.py"), "--check"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_addresses_unique_aligned_and_in_range():
    from golden.regmap_gen import ADDR
    values = list(ADDR.values())
    assert len(values) == len(set(values)), "duplicate register addresses"
    assert all(0 <= v < 4096 for v in values), "address outside 12-bit window"
    assert all(v % 4 == 0 for v in values), "register not word-aligned"


def test_key_registers_present():
    from golden.regmap_gen import ADDR, ACCESS, FIELDS
    # Traceability: identity, core enable, config, pass sequencing,
    # observability counters, ECC injection hook, AER access.
    for name in ("ID", "VERSION", "CTRL", "STATUS", "STATUS_CLR",
                 "CFG_NEUR", "CFG_AXON", "CFG_THRESH", "CFG_VRESET",
                 "CFG_LEAK", "CFG_SYNSHIFT", "CFG_REFR", "CFG_FLAGS",
                 "PASS_TILE_OFF", "W_BASE", "W_ADDR", "W_DATA_LO",
                 "W_DATA_HI", "N_ADDR", "N_DATA",
                 "CNT_SEC", "CNT_DED", "CNT_EVQ_OVF", "CNT_AXON_OOR",
                 "FAULT_ADDR", "ECC_INJ", "FAULT_CLR",
                 "EVQ_STAT", "EVQ_IN", "EVQ_OUT", "NODE_ID"):
        assert name in ADDR, f"missing register {name}"
    assert ACCESS["ID"] == "RO"
    assert ACCESS["STATUS_CLR"] == "W1C"
    assert ACCESS["FAULT_CLR"] == "W1C"
    assert "EN" in FIELDS["CTRL"]
    assert "SINGLE" in FIELDS["ECC_INJ"] and "DOUBLE" in FIELDS["ECC_INJ"]
    assert "OVF_SEEN" in FIELDS["STATUS"]


def test_identity_words():
    """ID is the ASCII "NPU1" discovery constant (vendor byte 0x4E "N"
    leading, GRLIB-plug-and-play-inspired fixed word at the block base);
    VERSION starts at 1."""
    from golden.regmap_gen import ADDR, RESET
    assert ADDR["ID"] == 0x00, "discovery word must sit at the block base"
    assert RESET["ID"] == int.from_bytes(b"NPU1", "big")
    assert (RESET["ID"] >> 24) == 0x4E, "vendor byte must be 0x4E"
    assert RESET["VERSION"] >= 1


def test_reset_values_consistent_with_fields():
    """Spec resets: CTRL.SCRUB_EN = 1, STATUS EVQ_*_EMPTY = 1, CFG_FLAGS
    LEAK_EN = 1; CFG_NEUR/CFG_AXON reset to the full default core (512,
    docs/02 candidate B working point)."""
    from golden.regmap_gen import FIELDS, RESET
    assert (RESET["CTRL"] >> FIELDS["CTRL"]["SCRUB_EN"]) & 1 == 1
    assert (RESET["STATUS"] >> FIELDS["STATUS"]["EVQ_IN_EMPTY"]) & 1 == 1
    assert (RESET["STATUS"] >> FIELDS["STATUS"]["EVQ_OUT_EMPTY"]) & 1 == 1
    assert (RESET["CFG_FLAGS"] >> FIELDS["CFG_FLAGS"]["LEAK_EN"]) & 1 == 1
    assert RESET["CFG_NEUR"] == 512 and RESET["CFG_AXON"] == 512


def test_fields_fit_inside_registers():
    from golden.regmap_gen import FIELDS, FIELD_WIDTHS
    for reg, fields in FIELDS.items():
        for name, lsb in fields.items():
            width = FIELD_WIDTHS[reg][name]
            assert 0 <= lsb and lsb + width <= 32, f"{reg}.{name} out of range"


def _spec_registers():
    """Parse the docs/10 section 10 register tables: rows of the form
    | 0xNN | NAME | ACCESS | RESET | desc |. Returns name -> (offset,
    access, reset-or-None)."""
    text = (ROOT / "docs" / "10-npu-mvp-spec.md").read_text()
    section = text.split("## 10. Register list", 1)[1].split("\n## 11.", 1)[0]
    row = re.compile(
        r"^\|\s*(0x[0-9A-Fa-f]+)\s*\|\s*(\w+)\s*\|\s*(RO|RW|WO|W1C)\s*\|"
        r"\s*([^|]*?)\s*\|", re.M)
    regs = {}
    for off, name, access, reset in row.findall(section):
        m = re.match(r"0x[0-9A-Fa-f]+$", reset)
        regs[name] = (int(off, 16), access, int(reset, 16) if m else None)
    return regs


def test_yaml_matches_spec_section_10():
    """Every register in docs/10 section 10 must exist in the YAML with
    the same offset and access, and the same reset where the spec gives a
    hex literal (symbolic resets like N_NEURONS are checked elsewhere)."""
    from golden.regmap_gen import ADDR, ACCESS, RESET
    spec = _spec_registers()
    assert len(spec) >= 30, "spec table parse failure"
    for name, (off, access, reset) in spec.items():
        assert name in ADDR, f"spec register {name} missing from YAML"
        assert ADDR[name] == off, f"{name}: YAML 0x{ADDR[name]:02X} != spec 0x{off:02X}"
        assert ACCESS[name] == access, f"{name}: access mismatch"
        if reset is not None:
            assert RESET[name] == reset, f"{name}: reset mismatch"
    extra = set(ADDR) - set(spec)
    assert not extra, f"YAML registers not in the spec: {sorted(extra)}"


# ---------------------------------------------------------------------
# Golden-model bit constants against the generated map
# ---------------------------------------------------------------------
#
# sw/golden/secded.py models the fault-counter block, so it has to name
# the clear bits of FAULT_CLR (0x88) and the STATUS bit DED_SEEN. It
# writes them as literals, which is a second copy of a position
# regmap.yaml already owns. These tests are that copy's sync check, in
# the same spirit as test_generated_files_in_sync above: a YAML edit that
# moves, renames or adds a bit fails here instead of leaving the golden
# model silently pointing at the old position.


def _fault_clr_constants():
    """The FAULT_CLR_<FIELD> constants sw/golden/secded.py exports.

    FAULT_CLR_ALL is the union, not a field, and is checked separately.
    """
    from golden import secded
    return {name[len("FAULT_CLR_"):]: getattr(secded, name)
            for name in dir(secded)
            if name.startswith("FAULT_CLR_") and name != "FAULT_CLR_ALL"}


def test_secded_fault_clr_constants_cover_exactly_the_yaml_fields():
    """One constant per declared FAULT_CLR field, and no orphans.

    A field added to the YAML without a constant, or a constant left
    behind after its field was renamed away, fails here.
    """
    from golden.regmap_gen import FIELDS
    declared = set(FIELDS["FAULT_CLR"])
    modelled = set(_fault_clr_constants())
    assert modelled == declared, (
        f"sw/golden/secded.py FAULT_CLR constants and regmap.yaml fields "
        f"disagree; YAML only: {sorted(declared - modelled)}, "
        f"secded.py only: {sorted(modelled - declared)}")


def test_secded_fault_clr_constants_are_the_yaml_bit_positions():
    from golden.regmap_gen import FIELDS, FIELD_WIDTHS
    for field, value in _fault_clr_constants().items():
        bit = FIELDS["FAULT_CLR"][field]
        width = FIELD_WIDTHS["FAULT_CLR"][field]
        assert width == 1, f"FAULT_CLR.{field} is {width} bits, not a flag"
        assert value == 1 << bit, (
            f"FAULT_CLR_{field} = 0x{value:X}, YAML puts the field at bit "
            f"{bit} (0x{1 << bit:X})")


def test_secded_fault_clr_all_is_the_union_of_the_declared_bits():
    from golden.regmap_gen import FIELDS
    from golden.secded import FAULT_CLR_ALL
    union = 0
    for bit in FIELDS["FAULT_CLR"].values():
        union |= 1 << bit
    assert FAULT_CLR_ALL == union, (
        f"FAULT_CLR_ALL = 0x{FAULT_CLR_ALL:X}, the declared fields cover "
        f"0x{union:X}")


def test_secded_status_ded_seen_constant_is_the_yaml_bit_position():
    from golden.regmap_gen import FIELDS, FIELD_WIDTHS
    from golden.secded import STATUS_DED_SEEN
    bit = FIELDS["STATUS"]["DED_SEEN"]
    assert FIELD_WIDTHS["STATUS"]["DED_SEEN"] == 1
    assert STATUS_DED_SEEN == 1 << bit, (
        f"STATUS_DED_SEEN = 0x{STATUS_DED_SEEN:X}, YAML puts STATUS.DED_SEEN "
        f"at bit {bit} (0x{1 << bit:X})")


def test_fault_clr_bits_follow_fault_block_offset_order():
    """RTL header convention C2, restated in sw/golden/secded.py: one bit
    per fault-block register, in offset order from 0x70 upward, packed
    from bit 0. The register bank's packed counter vector and the
    exported fault_clr[4:0] port both assume it."""
    from golden.regmap_gen import ADDR, FIELDS
    fields = FIELDS["FAULT_CLR"]
    by_bit = sorted(fields, key=lambda name: fields[name])
    assert [fields[name] for name in by_bit] == list(range(len(by_bit))), (
        f"FAULT_CLR bits are not packed from 0: {fields}")
    for name in by_bit:
        assert name in ADDR, (
            f"FAULT_CLR.{name} names no register; the one-bit-per-register "
            f"convention no longer holds")
    offsets = [ADDR[name] for name in by_bit]
    assert offsets == sorted(offsets), (
        f"FAULT_CLR bit order {by_bit} is not fault-block offset order "
        f"{[f'0x{o:02X}' for o in offsets]}")
