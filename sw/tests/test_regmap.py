"""Register map consistency tests (single-source discipline).

The YAML source (regmap/regmap.yaml) must stay in sync with both the
generated files and the normative register list in docs/10-npu-mvp-spec.md
section 10 ("must not diverge once the regmap flow is instantiated").
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
