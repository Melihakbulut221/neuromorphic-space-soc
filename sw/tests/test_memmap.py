"""SoC memory map consistency tests (single-source discipline).

The YAML source (regmap/memmap.yaml) must stay in sync with the six files
generated from it, and the map itself must satisfy the properties the
fabric's address decoder and Ibex's fixed vectors depend on. This is the
sibling of test_regmap.py and follows the same rule: the source is one
file, everything else is generated, and a stale generated file is a test
failure rather than something a reader has to notice.

The properties fall into four groups:

  1. Generation. The committed generated files match the YAML.
  2. Decodability. Every region is a naturally aligned power of two and
     no two overlap, so address decode is a prefix compare and never a
     magnitude comparison, and no address is claimed twice.
  3. Ibex reachability. docs/38-ibex-bringup.md section 7.5 defects 3 and
     4: the core resets to {boot_addr_i[31:8], 8'h80} and forces
     mtvec[7:2] to zero. A map that puts the reset vector or a trap
     vector where the core cannot reach it is wrong on arrival, and these
     tests are what make that a mechanical check rather than a comment.
  4. Cross-artifact agreement. The same address must appear identically
     in the Verilog header, the C header, the linker script, the device
     table contents and the documentation. Each of those is consumed by a
     different tool, so a generator that emitted them inconsistently
     would fail in five different places at five different times.

WHAT THIS FILE DOES NOT COVER, stated because a green result here is
narrower than "the memory map works":

  * It does not simulate anything. That the RTL decodes what the map says
    is checked by hw/soc/tb/cocotb/test_soc_bus.py against the same
    generated constants, and end to end by hw/soc/flow/sim_soc.sh.
  * It does not check that a region's size is sensible, only that it is
    decodable. A 4 GiB RAM would pass every test here.
  * The RTL cross-check in test_fabric_decodes_every_ported_region is
    TEXTUAL. It confirms that soc_bus.v mentions the generated constants
    for each ported region and mentions no others; it cannot confirm that
    it uses them correctly. That is the formal job's F2, and the two are
    complementary: the formal proof cannot enumerate the map and this
    test cannot read the logic.
  * Nothing here says anything about the reserved regions beyond their
    addresses. Fourteen of the sixteen peripheral slots and six of the ten
    regions have no implementation at all.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sw"))

SOC_RTL = ROOT / "hw" / "soc" / "rtl"
SOC_SW = ROOT / "hw" / "soc" / "tb" / "sw"


# ----------------------------------------------------------------------
# 1. Generation
# ----------------------------------------------------------------------


def test_generated_files_in_sync():
    """The committed generated files must match the YAML source exactly."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "regmap" / "generate_memmap.py"), "--check"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_declared_output_exists():
    from golden import memmap_gen  # noqa: F401  (import must succeed)
    for path in (
        ROOT / "docs" / "memmap-soc.md",
        ROOT / "sw" / "golden" / "memmap_gen.py",
        SOC_RTL / "soc_memmap.vh",
        SOC_RTL / "soc_pnp_rom.vh",
        SOC_RTL / "soc_apb_pnp_rom.vh",
        SOC_SW / "soc_memmap.h",
        SOC_SW / "memmap.ld",
    ):
        assert path.is_file(), f"{path.relative_to(ROOT)} was not generated"


# ----------------------------------------------------------------------
# 2. Decodability
# ----------------------------------------------------------------------


def test_every_region_is_a_naturally_aligned_power_of_two():
    """Prefix-compare decode is only correct under this condition.

    A region whose size is not a power of two, or whose base is not a
    multiple of its size, cannot be selected by `addr & MASK == BASE`;
    it needs two comparators and a carry chain in the address path.
    """
    from golden.memmap_gen import REGIONS
    for name, (base, size, _t, _a, _s, _p) in REGIONS.items():
        assert size > 0 and (size & (size - 1)) == 0, \
            f"{name}: size 0x{size:X} is not a power of two"
        assert base % size == 0, \
            f"{name}: base 0x{base:08X} is not aligned to size 0x{size:X}"


def test_masks_are_the_prefix_masks_of_their_sizes():
    from golden.memmap_gen import REGIONS, MASKS
    for name, (base, size, _t, _a, _s, _p) in REGIONS.items():
        assert MASKS[name] == (0xFFFFFFFF & ~(size - 1)), \
            f"{name}: mask does not match size"
        assert base & MASKS[name] == base, f"{name}: base is not its own prefix"


def test_no_two_regions_overlap():
    from golden.memmap_gen import REGIONS
    ordered = sorted(REGIONS.items(), key=lambda kv: kv[1][0])
    for (an, (ab, asz, *_)), (bn, (bb, *_)) in zip(ordered, ordered[1:]):
        assert ab + asz <= bb, \
            f"{an} (0x{ab:08X}+0x{asz:X}) overlaps {bn} (0x{bb:08X})"


def test_decode_is_unambiguous_at_every_region_boundary():
    """First and last word of every region select that region and no other.

    This is the property the fabric's one-hot decode rests on, checked
    over the map rather than over the RTL.
    """
    from golden.memmap_gen import REGIONS, MASKS
    for name, (base, size, *_rest) in REGIONS.items():
        for addr in (base, base + size - 4, base + (size // 2)):
            hits = [n for n, m in MASKS.items() if addr & m == REGIONS[n][0]]
            assert hits == [name], \
                f"0x{addr:08X} (in {name}) also decodes as {set(hits) - {name}}"


def test_every_region_fits_in_the_address_space():
    from golden.memmap_gen import REGIONS
    for name, (base, size, *_rest) in REGIONS.items():
        assert base + size <= 1 << 32, f"{name} runs off the 32-bit space"


def test_implemented_regions_name_a_fabric_port_and_reserved_ones_do_not():
    from golden.memmap_gen import REGIONS
    for name, (_b, _s, _t, _a, status, port) in REGIONS.items():
        if status == "implemented":
            assert port is not None, f"{name} is implemented but has no port"
        else:
            assert port is None, \
                f"{name} is reserved but names port {port!r}; an access to it " \
                "must reach the error slave"


def test_fabric_ports_are_unique():
    from golden.memmap_gen import PORTS, REGIONS
    ported = {n for n, r in REGIONS.items() if r[5] is not None}
    assert set(PORTS.values()) == ported
    assert len(PORTS) == len(ported), "two regions share one fabric port"


# ----------------------------------------------------------------------
# 3. Ibex reachability
# ----------------------------------------------------------------------


def test_reset_vector_is_the_one_ibex_actually_fetches():
    """Ibex resets to {boot_addr_i[31:8], 8'h80}.

    Two consequences, both checked: the offset is 0x80 and cannot be
    chosen, and the low byte of boot_addr_i is discarded by the core, so
    a boot region whose base had a non-zero low byte would put the reset
    vector somewhere other than where the base says.
    """
    from golden.memmap_gen import BOOT_ADDR, RESET_VECTOR, REGIONS
    assert RESET_VECTOR == (BOOT_ADDR & 0xFFFFFF00) | 0x80
    assert BOOT_ADDR & 0xFF == 0, "boot region base has a non-zero low byte"
    boot = [n for n, r in REGIONS.items() if r[0] == BOOT_ADDR]
    assert len(boot) == 1, "boot address does not name exactly one region"
    base, size, _t, attr, status, _p = REGIONS[boot[0]]
    assert base <= RESET_VECTOR < base + size, \
        "the reset vector is outside the boot region"
    assert "x" in attr, "the boot region must be executable"
    assert status == "implemented", \
        "a core that resets into the error slave cannot start"


def test_every_region_base_can_hold_a_trap_vector():
    """Ibex forces mtvec[7:2] to zero and has no direct mode.

    A trap vector written to any 4-byte-aligned address is silently
    truncated to the enclosing 256-byte boundary. Requiring every region
    base to be 256-byte aligned means the map is never the reason a
    handler ends up somewhere else.
    """
    from golden.memmap_gen import REGIONS, BASE_ALIGNMENT
    assert BASE_ALIGNMENT == 0x100
    for name, (base, *_rest) in REGIONS.items():
        assert base % BASE_ALIGNMENT == 0, \
            f"{name}: base 0x{base:08X} is not 256-byte aligned"


def test_apb_slots_are_inside_the_bridge_window_and_derived_from_it():
    from golden.memmap_gen import APB_BASE, APB_SIZE, APB_SLOT_SIZE, APB_SLOTS
    seen = {}
    for name, (addr, slot, _irq, _status) in APB_SLOTS.items():
        assert addr == APB_BASE + slot * APB_SLOT_SIZE, \
            f"{name}: address is not derived from its slot index"
        assert APB_BASE <= addr < APB_BASE + APB_SIZE, \
            f"{name}: outside the bridge window"
        assert addr % APB_SLOT_SIZE == 0
        assert slot not in seen, f"{name} and {seen[slot]} share slot 0x{slot:03X}"
        seen[slot] = name


def test_apb_offsets_fit_the_bridge_address_width():
    """The bridge carries a 20-bit offset, so the window must be 1 MiB.

    hw/soc/formal/soc_apb_bridge_props.v proves paddr_o carries
    addr_i[19:0] and explicitly defers to this test the question of
    whether discarding the upper bits is safe.
    """
    from golden.memmap_gen import APB_SIZE, APB_SLOTS, APB_BASE
    assert APB_SIZE == 1 << 20
    for name, (addr, _slot, _irq, _st) in APB_SLOTS.items():
        assert (addr - APB_BASE) < (1 << 20), f"{name}: offset exceeds 20 bits"


def test_interrupt_numbers_are_unique_and_fit_the_record_field():
    """The plug-and-play identification word carries irq in bits [4:0]."""
    from golden.memmap_gen import APB_SLOTS
    claimed = [irq for (_a, _s, irq, _st) in APB_SLOTS.values() if irq]
    assert len(claimed) == len(set(claimed)), \
        f"interrupt sources are not unique: {sorted(claimed)}"
    assert all(0 < irq < 32 for irq in claimed)


# ----------------------------------------------------------------------
# 4. Cross-artifact agreement
# ----------------------------------------------------------------------


def _verilog_constants():
    text = (SOC_RTL / "soc_memmap.vh").read_text()
    return {m.group(1): int(m.group(2), 16) for m in
            re.finditer(r"localparam \[31:0\] (\w+)\s*=\s*32'h([0-9A-Fa-f]+);", text)}


def _c_constants():
    text = (SOC_SW / "soc_memmap.h").read_text()
    return {m.group(1): int(m.group(2), 16) for m in
            re.finditer(r"#define (\w+)\s+0x([0-9A-Fa-f]+)u", text)}


def test_verilog_and_c_headers_agree_with_the_python_map():
    from golden.memmap_gen import REGIONS, MASKS, RESET_VECTOR, BOOT_ADDR
    v, c = _verilog_constants(), _c_constants()
    assert v["SOC_RESET_VECTOR"] == RESET_VECTOR == c["SOC_RESET_VECTOR"]
    assert v["SOC_BOOT_ADDR"] == BOOT_ADDR == c["SOC_BOOT_ADDR"]
    for name, (base, size, *_rest) in REGIONS.items():
        assert v[f"SOC_BASE_{name}"] == base
        assert v[f"SOC_SIZE_{name}"] == size
        assert v[f"SOC_MASK_{name}"] == MASKS[name]
        assert c[f"SOC_{name}_BASE"] == base
        assert c[f"SOC_{name}_SIZE"] == size


def test_c_header_carries_every_apb_slot_address():
    from golden.memmap_gen import APB_SLOTS
    c = _c_constants()
    for name, (addr, *_rest) in APB_SLOTS.items():
        assert c[f"SOC_{name}_BASE"] == addr


def test_linker_memory_block_places_text_on_the_reset_vector():
    """The linker is the tool that gets this wrong, and it did once.

    docs/38 section 7.5 defect 4: a link script that moved _start off the
    reset vector produced garbled output rather than a crash. The ROM
    MEMORY region therefore starts AT the reset vector, not at the region
    base, and that is generated rather than typed.
    """
    from golden.memmap_gen import RESET_VECTOR, REGIONS, BOOT_ADDR
    text = (SOC_SW / "memmap.ld").read_text()
    rom = re.search(r"rom\s*\(rx\)\s*:\s*ORIGIN\s*=\s*0x([0-9A-Fa-f]+),"
                    r"\s*LENGTH\s*=\s*0x([0-9A-Fa-f]+)", text)
    assert rom, "memmap.ld has no rom MEMORY region"
    assert int(rom.group(1), 16) == RESET_VECTOR
    boot = next(r for r in REGIONS.values() if r[0] == BOOT_ADDR)
    assert int(rom.group(2), 16) == boot[1] - (RESET_VECTOR - BOOT_ADDR)

    ram = re.search(r"ram\s*\(rwx\)\s*:\s*ORIGIN\s*=\s*0x([0-9A-Fa-f]+),"
                    r"\s*LENGTH\s*=\s*0x([0-9A-Fa-f]+)", text)
    assert ram, "memmap.ld has no ram MEMORY region"
    assert int(ram.group(1), 16) == REGIONS["RAM"][0]
    assert int(ram.group(2), 16) == REGIONS["RAM"][1]
    assert f"__soc_reset_vector = 0x{RESET_VECTOR:08X};" in text


def test_device_table_has_a_record_for_every_region():
    """One eight-word slave record per region, in address order, at the
    GRLIB record offsets. The identification word must carry the vendor
    code, and user word 1 must carry the exact size the bank address
    register cannot express below 1 MiB granularity."""
    from golden.memmap_gen import PNP_ROM, REGIONS, VENDOR_ID
    ordered = sorted(REGIONS.items(), key=lambda kv: kv[1][0])
    for i, (name, (base, size, _t, _a, status, _p)) in enumerate(ordered):
        w = 0x200 + i * 8
        assert w in PNP_ROM, f"{name} has no device table record"
        assert (PNP_ROM[w] >> 24) == VENDOR_ID, f"{name}: wrong vendor byte"
        assert PNP_ROM[w + 1] == size, f"{name}: user word 1 is not the size"
        assert PNP_ROM.get(w + 2, 0) == (1 if status == "implemented" else 0)


def test_device_table_identity_and_endianness_words():
    """0xFFFFFFF0 carries the identity, 0xFFFFFFF4 the endianness flag,
    and bit 0 must say little endian: this is an RV32 part."""
    from golden.memmap_gen import PNP_ROM
    assert 0x3FC in PNP_ROM and 0x3FD in PNP_ROM
    assert PNP_ROM[0x3FD] & 1 == 1, "endianness word must report little endian"


def test_apb_device_table_records_match_the_slot_addresses():
    """The peripheral bank address register compares address bits [19:8],
    so a 4 KiB slot is expressible exactly and the record's address field
    must be the slot offset in 256-byte units."""
    from golden.memmap_gen import APB_PNP_ROM, APB_SLOTS, APB_BASE, VENDOR_ID
    ordered = sorted(APB_SLOTS.items(), key=lambda kv: kv[1][1])
    for i, (name, (addr, _slot, irq, _st)) in enumerate(ordered):
        ident, bar = APB_PNP_ROM[i * 2], APB_PNP_ROM[i * 2 + 1]
        assert (ident >> 24) == VENDOR_ID, f"{name}: wrong vendor byte"
        assert (ident & 0x1F) == irq, f"{name}: record irq does not match the map"
        assert (bar >> 20) == ((addr - APB_BASE) >> 8), \
            f"{name}: record address field does not match the slot"
        assert (bar & 0xF) == 0b0001, f"{name}: record type is not peripheral I/O"


def test_documentation_names_every_region_and_slot():
    from golden.memmap_gen import REGIONS, APB_SLOTS
    text = (ROOT / "docs" / "memmap-soc.md").read_text()
    for name, (base, *_rest) in REGIONS.items():
        assert f"`0x{base:08X}`" in text, f"{name} base missing from the document"
        assert f"| {name} |" in text, f"{name} missing from the document"
    for name, (addr, *_rest) in APB_SLOTS.items():
        assert f"`0x{addr:08X}`" in text, f"{name} address missing"


# ----------------------------------------------------------------------
# 5. The map against the RTL that decodes it
# ----------------------------------------------------------------------


def test_fabric_decodes_every_ported_region_and_no_other():
    """Textual, and deliberately so.

    hw/soc/formal/soc_bus.sby proves the decode is correct for the four
    regions the RTL names, but a formal job cannot enumerate the map: if
    a region were added to regmap/memmap.yaml with a fabric port and
    soc_bus.v were not extended, every property there would still pass
    and the new region would silently reach the error slave. This test is
    the other half of that pair. It cannot check that the constants are
    used correctly -- that is what the formal job is for.
    """
    from golden.memmap_gen import REGIONS
    src = (SOC_RTL / "soc_bus.v").read_text()
    named = set(re.findall(r"SOC_MASK_(\w+)", src))
    ported = {n for n, r in REGIONS.items() if r[5] is not None}
    assert named == ported, (
        f"soc_bus.v decodes {sorted(named)} but the map's ported regions are "
        f"{sorted(ported)}")
    for name in ported:
        assert f"SOC_BASE_{name}" in src, \
            f"soc_bus.v uses SOC_MASK_{name} without SOC_BASE_{name}"


def test_top_level_decodes_the_implemented_apb_slots():
    """Same argument, one level down: soc_top.v owns the peripheral slot
    decode (the bridge deliberately does not), so it must name exactly
    the slots the map marks implemented."""
    from golden.memmap_gen import APB_SLOTS
    src = (SOC_RTL / "soc_top.v").read_text()
    named = set(re.findall(r"SOC_APBSLOT_(\w+)", src))
    implemented = {n for n, s in APB_SLOTS.items() if s[3] == "implemented"}
    assert named == implemented, (
        f"soc_top.v decodes slots {sorted(named)} but the map marks "
        f"{sorted(implemented)} implemented")
