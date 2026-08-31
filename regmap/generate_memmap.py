"""SoC memory map generator.

Reads regmap/memmap.yaml (the single source) and emits:
  - docs/memmap-soc.md            documentation tables
  - sw/golden/memmap_gen.py       Python constants for tests and hosts
  - hw/soc/rtl/soc_memmap.vh      Verilog localparams for the RTL
  - hw/soc/rtl/soc_pnp_rom.vh     the device table ROM contents
  - hw/soc/tb/sw/soc_memmap.h     C constants for the bare-metal program
  - hw/soc/tb/sw/memmap.ld        the linker MEMORY block

Run from anywhere:  python regmap/generate_memmap.py
`--check` exits non-zero if any output is stale. sw/tests/test_memmap.py
runs that, so regeneration is enforced by the suite rather than by memory.

This is deliberately a SECOND generator alongside regmap/generate.py
rather than an extension of it. generate.py writes hw/rtl/npu_regs.vh,
and hw/rtl/ is pinned by git blob hash in docs/34-pilot-freeze.md section
2.1 for the duration of the TTIHP26b shuttle. Nothing here may write into
that directory, and the cheapest way to guarantee that is for the two
generators to have disjoint output sets.

WHAT THE VALIDATION DOES NOT COVER. It checks the map's internal
consistency -- alignment, power-of-two sizing, non-overlap, containment,
uniqueness, field widths -- and the two Ibex reachability constraints of
docs/38 section 7.5. It does NOT check that the RTL decodes what this
file says; that is the job of the cocotb suite in hw/soc/tb/cocotb/,
which imports the generated Python constants and drives the fabric
against them. A map that is self-consistent and an interconnect that
ignores it would both pass here.
"""

import re
import sys
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "regmap" / "memmap.yaml"

HEADER = "GENERATED FILE - edit regmap/memmap.yaml and run regmap/generate_memmap.py"

# GRLIB plug-and-play record field widths (grlib.pdf section 5.3). The
# identification word is vendor[31:24] device[23:12] version[9:5]
# irq[4:0]; a bank address register is addr[31:20] prefetch[17]
# cacheable[16] mask[15:4] type[3:0].
VENDOR_BITS, DEVICE_BITS, VERSION_BITS, IRQ_BITS = 8, 12, 5, 5
BAR_TYPE_APB_IO = 0b0001
BAR_TYPE_MEM = 0b0010
BAR_TYPE_IO = 0b0011

# An AHB-style bank address register compares address bits [31:20], so
# its granularity is 1 MiB and it cannot express a region smaller than
# that. Three regions in this map are smaller. The exact byte size goes
# in user-defined word 1, which GRLIB leaves free, and the doc says so.
BAR_GRANULARITY = 1 << 20
APB_BAR_GRANULARITY = 1 << 8

PNP_WORDS = 1024  # 4 KiB window / 4
PNP_MASTER_RECORDS = 64
PNP_SLAVE_BASE_WORD = 0x800 // 4
PNP_RECORD_WORDS = 8


def die(msg):
    sys.exit(f"error: {msg}")


def load():
    spec = yaml.safe_load(SRC.read_text())
    validate(spec)
    return spec


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


def _is_pow2(n):
    return n > 0 and (n & (n - 1)) == 0


def validate(spec):
    meta = spec["meta"]
    space = 1 << meta["addr_bits"]
    align = meta["base_alignment"]
    regions = spec["regions"]

    if not _is_pow2(align):
        die(f"meta.base_alignment 0x{align:X} is not a power of two")
    if meta["vendor_id"] >> VENDOR_BITS:
        die(f"meta.vendor_id 0x{meta['vendor_id']:X} wider than {VENDOR_BITS} bits")

    seen_names = set()
    seen_dev = {}
    for r in regions:
        name, base, size = r["name"], r["base"], r["size"]
        if not NAME_RE.match(str(name)):
            die(f"region name {name!r} must be upper-case identifier-shaped")
        if name in seen_names:
            die(f"duplicate region name {name}")
        seen_names.add(name)
        if not _is_pow2(size):
            die(f"{name}: size 0x{size:X} is not a power of two; "
                "decode would need a magnitude comparison")
        if base % size:
            die(f"{name}: base 0x{base:08X} is not naturally aligned to its "
                f"size 0x{size:X}; decode would need a magnitude comparison")
        if base % align:
            die(f"{name}: base 0x{base:08X} is not 0x{align:X}-aligned. Ibex "
                "forces mtvec[7:2] to zero, so a trap vector placed at this "
                "region's base would be silently relocated "
                "(docs/38 section 7.5 defect 3)")
        if base + size > space:
            die(f"{name}: 0x{base:08X}+0x{size:X} runs off the "
                f"{meta['addr_bits']}-bit space")
        if r["device_id"] >> DEVICE_BITS:
            die(f"{name}: device_id 0x{r['device_id']:X} wider than {DEVICE_BITS} bits")
        if r["status"] not in ("implemented", "reserved"):
            die(f"{name}: status {r['status']!r} must be implemented or reserved")
        if r["type"] not in ("memory", "io"):
            die(f"{name}: type {r['type']!r} must be memory or io")
        if r["status"] == "implemented" and "port" not in r:
            die(f"{name}: status implemented but no fabric port named")

    # Non-overlap, checked pairwise against sorted order.
    ordered = sorted(regions, key=lambda r: r["base"])
    for a, b in zip(ordered, ordered[1:]):
        if a["base"] + a["size"] > b["base"]:
            die(f"{a['name']} (0x{a['base']:08X}+0x{a['size']:X}) overlaps "
                f"{b['name']} (0x{b['base']:08X})")

    # Fabric ports must be distinct: two regions sharing one port would
    # make the response routing ambiguous.
    ports = [r["port"] for r in regions if "port" in r]
    if len(ports) != len(set(ports)):
        die(f"fabric port names are not unique: {ports}")

    # ---- the two Ibex constraints, checked rather than commented ----
    boot = by_name(regions, meta["boot_region"])
    if boot is None:
        die(f"meta.boot_region {meta['boot_region']!r} names no region")
    off = meta["reset_vector_offset"]
    if off != 0x80:
        die(f"meta.reset_vector_offset 0x{off:X}: Ibex resets to "
            "{boot_addr_i[31:8], 8'h80}, so the offset is 0x80 and nothing "
            "else (docs/38 section 7.5 defect 4)")
    if boot["base"] & 0xFF:
        die(f"boot region {boot['name']} base 0x{boot['base']:08X} has "
            "non-zero low byte; Ibex substitutes 8'h80 for boot_addr_i[7:0], "
            "so those bits are discarded and the reset vector would not be "
            "where the base says")
    if boot["size"] <= off:
        die(f"boot region {boot['name']} is 0x{boot['size']:X} bytes, which "
            f"does not contain the reset vector at +0x{off:X}")
    if "x" not in boot["attr"]:
        die(f"boot region {boot['name']} is not executable ({boot['attr']}); "
            "the reset vector must be fetchable")
    if boot["status"] != "implemented":
        die(f"boot region {boot['name']} is {boot['status']}; a core that "
            "resets into the error slave cannot start")

    # ---- APB slots ----
    apb = by_name(regions, "APB")
    if apb is None:
        die("no region named APB; the peripheral bus window must exist")
    slot_size = 1 << 12
    seen_slots = {}
    seen_slot_names = set()
    for s in spec["apb_slots"]:
        name, slot = s["name"], s["slot"]
        if not NAME_RE.match(str(name)):
            die(f"APB slot name {name!r} must be upper-case identifier-shaped")
        if name in seen_slot_names or name in seen_names:
            die(f"APB slot {name} collides with another slot or a region name")
        seen_slot_names.add(name)
        if slot in seen_slots:
            die(f"APB slots {name} and {seen_slots[slot]} share index 0x{slot:03X}")
        seen_slots[slot] = name
        if (slot + 1) * slot_size > apb["size"]:
            die(f"APB slot {name} index 0x{slot:03X} runs past the "
                f"0x{apb['size']:X}-byte bridge window")
        if s["irq"] >> IRQ_BITS:
            die(f"{name}: irq {s['irq']} wider than {IRQ_BITS} bits; the "
                "plug-and-play identification word cannot carry it")
        if s["device_id"] >> DEVICE_BITS:
            die(f"{name}: device_id 0x{s['device_id']:X} wider than {DEVICE_BITS} bits")
        if s["status"] not in ("implemented", "reserved"):
            die(f"{name}: status {s['status']!r} must be implemented or reserved")

    # Interrupt numbers must be unique among the slots that claim one.
    irqs = [s["irq"] for s in spec["apb_slots"] if s["irq"]]
    if len(irqs) != len(set(irqs)):
        die(f"interrupt source numbers are not unique: {sorted(irqs)}")

    for r in regions:
        seen_dev.setdefault(r["device_id"], r["name"])


def by_name(items, name):
    for i in items:
        if i["name"] == name:
            return i
    return None


# ---------------------------------------------------------------------
# Derived quantities
# ---------------------------------------------------------------------


def reset_vector(spec):
    boot = by_name(spec["regions"], spec["meta"]["boot_region"])
    return boot["base"] + spec["meta"]["reset_vector_offset"]


def region_mask(r, bits=32):
    """The prefix-compare mask. `addr & mask == base` selects the region,
    which is only a correct decode because validate() has already
    required a naturally aligned power-of-two size."""
    return ((1 << bits) - 1) & ~(r["size"] - 1)


def apb_addr(spec, s):
    return by_name(spec["regions"], "APB")["base"] + s["slot"] * 0x1000


def ident_word(vendor, device, version, irq):
    return ((vendor & 0xFF) << 24 | (device & 0xFFF) << 12
            | (version & 0x1F) << 5 | (irq & 0x1F))


def bar_word(base, size, bar_type, granularity, prefetch=0, cacheable=0):
    """A GRLIB bank address register.

    `size` is rounded UP to `granularity` because the field cannot
    express anything finer. gen_markdown reports where that rounding
    happened; the exact size is carried in user-defined word 1.
    """
    rounded = max(granularity, 1 << (size - 1).bit_length())
    addr_field = (base // granularity) & 0xFFF
    mask_field = ((0x1000 - rounded // granularity) & 0xFFF)
    return (addr_field << 20 | (prefetch & 1) << 17 | (cacheable & 1) << 16
            | mask_field << 4 | (bar_type & 0xF))


def bar_is_exact(size, granularity):
    return size >= granularity


# ---------------------------------------------------------------------
# The device table ROM
# ---------------------------------------------------------------------


def pnp_words(spec):
    """word index (0..1023) -> value, for every non-zero word.

    Layout is GRLIB's (grlib.pdf section 5.3): master records from word
    0, slave records from word 0x200, eight words each. The two masters
    are Ibex's instruction and data ports, which are separate masters on
    this fabric and are arbitrated as such.
    """
    meta = spec["meta"]
    ver = int(float(meta["version"]) * 10) & 0x1F
    words = {}

    # Masters: the CPU's two ports.
    for i, (dev, _label) in enumerate([(0x00A, "Ibex instruction port"),
                                       (0x00B, "Ibex data port")]):
        words[i * PNP_RECORD_WORDS] = ident_word(meta["vendor_id"], dev, ver, 0)

    # Slaves: one record per region, in address order.
    for i, r in enumerate(sorted(spec["regions"], key=lambda x: x["base"])):
        w = PNP_SLAVE_BASE_WORD + i * PNP_RECORD_WORDS
        words[w] = ident_word(meta["vendor_id"], r["device_id"], ver, 0)
        # User-defined word 1 carries the exact byte size, which the BAR
        # cannot express below 1 MiB granularity.
        words[w + 1] = r["size"]
        # User-defined word 2 carries the status: 1 = implemented.
        words[w + 2] = 1 if r["status"] == "implemented" else 0
        words[w + 4] = bar_word(
            r["base"], r["size"],
            BAR_TYPE_MEM if r["type"] == "memory" else BAR_TYPE_IO,
            BAR_GRANULARITY,
            cacheable=1 if r["type"] == "memory" else 0)

    # The two top words: build/device identity and endianness.
    # grlib.pdf 5.3 puts the SoC device ID in the high half-word of
    # 0xFFFFFFF0 and the build ID in the low half; bit 0 of 0xFFFFFFF4
    # reports endianness, 1 = little. RV32 Ibex is little-endian.
    words[0x3FC] = (0x4E53 << 16) | (ver & 0xFFFF)   # "NS" + version
    words[0x3FD] = 1
    return words


def apb_pnp_words(spec):
    """word index within the APB PnP slot -> value. Two words per slot:
    identification and one bank address register. The APB bank address
    register compares address bits [19:8], so a 4 KiB slot is expressed
    exactly."""
    meta = spec["meta"]
    ver = int(float(meta["version"]) * 10) & 0x1F
    apb_base = by_name(spec["regions"], "APB")["base"]
    words = {}
    for i, s in enumerate(sorted(spec["apb_slots"], key=lambda x: x["slot"])):
        addr = apb_base + s["slot"] * 0x1000
        words[i * 2] = ident_word(meta["vendor_id"], s["device_id"], ver, s["irq"])
        # Offset within the 1 MiB window, in 256-byte units.
        words[i * 2 + 1] = bar_word(addr & 0xFFFFF, 0x1000, BAR_TYPE_APB_IO,
                                    APB_BAR_GRANULARITY)
    return words


# ---------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------


def gen_markdown(spec):
    meta = spec["meta"]
    rv = reset_vector(spec)
    boot = by_name(spec["regions"], meta["boot_region"])
    lines = [
        f"# SoC memory map v{meta['version']}",
        "",
        f"<!-- {HEADER} -->",
        "",
        "The frozen physical address map of the SoC. The normative source",
        "is `regmap/memmap.yaml`; this file is generated from it and",
        "`sw/tests/test_memmap.py` fails if it is stale.",
        "",
        "The interconnect this map sits on, and why it is not AMBA AHB, is",
        "`docs/39-soc-bus-and-memory-map.md`. The proposal this freezes is",
        "`docs/08-gr801-datasheet-notes.md` section 3.1.",
        "",
        "## 1. Reset and trap vectors",
        "",
        "| Property | Value | Why |",
        "|---|---|---|",
        f"| `boot_addr_i` | `0x{boot['base']:08X}` | base of the {boot['name']} region |",
        f"| Reset vector | `0x{rv:08X}` | Ibex resets to `{{boot_addr_i[31:8], 8'h80}}` |",
        f"| Trap vector alignment | {meta['base_alignment']} bytes | Ibex forces `mtvec[7:2]` to zero and has no direct mode |",
        "",
        "Both are `docs/38-ibex-bringup.md` section 7.5 defects 3 and 4.",
        "The generator refuses to emit a map whose boot region does not",
        "contain the reset vector, is not executable, or is not",
        "implemented, and refuses any region base that is not",
        f"{meta['base_alignment']}-byte aligned.",
        "",
        "## 2. System bus regions",
        "",
        "| Base | Last | Size | Name | Type | Attr | Status | Port | Description |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(spec["regions"], key=lambda x: x["base"]):
        lines.append(
            f"| `0x{r['base']:08X}` | `0x{r['base'] + r['size'] - 1:08X}` "
            f"| {human_size(r['size'])} | {r['name']} | {r['type']} "
            f"| {r['attr']} | {r['status']} | {r.get('port', '-')} "
            f"| {r['desc']} |")
    lines += [
        "",
        "Address decode is a prefix compare: a region is selected when",
        "`addr & MASK == BASE`. That is only a correct decode because every",
        "region is a naturally aligned power of two, which the generator",
        "enforces. Anything outside every region reaches the error slave",
        "and returns a bus error, which the core takes as an access fault.",
        "",
        "Provenance, one row per region:",
        "",
        "| Name | Address taken from |",
        "|---|---|",
    ]
    for r in sorted(spec["regions"], key=lambda x: x["base"]):
        lines.append(f"| {r['name']} | {r['source']} |")

    apb = by_name(spec["regions"], "APB")
    lines += [
        "",
        "## 3. Peripheral bus slots",
        "",
        f"One 4 KiB slot per peripheral inside the {human_size(apb['size'])}",
        f"window at `0x{apb['base']:08X}`. The bridge decodes `PADDR[19:12]`.",
        "Interrupt numbers are frozen here so the device table, the future",
        "interrupt controller and the drivers cannot disagree",
        "(`docs/08-gr801-datasheet-notes.md` section 4 item 7).",
        "",
        "| Address | Slot | Name | IRQ | Status | Description |",
        "|---|---|---|---|---|---|",
    ]
    for s in sorted(spec["apb_slots"], key=lambda x: x["slot"]):
        lines.append(
            f"| `0x{apb_addr(spec, s):08X}` | `0x{s['slot']:03X}` | {s['name']} "
            f"| {s['irq'] or '-'} | {s['status']} | {s['desc']} |")

    inexact = [r for r in spec["regions"]
               if not bar_is_exact(r["size"], BAR_GRANULARITY)]
    lines += [
        "",
        "## 4. Device table",
        "",
        f"A read-only table at `0x{by_name(spec['regions'], 'PNP')['base']:08X}`",
        "in GRLIB's plug-and-play record *layout* (`grlib.pdf` section 5.3):",
        "eight words per slave record from word `0x200`, master records from",
        "word `0x000`, identification word",
        "`vendor[31:24] device[23:12] version[9:5] irq[4:0]`, bank address",
        "register `addr[31:20] prefetch[17] cacheable[16] mask[15:4] type[3:0]`.",
        "",
        "**It is not an AMBA AHB plug-and-play table, because there is no AHB",
        "in this SoC.** The layout is mirrored because a well-known layout is",
        "what makes a device table readable; the bus underneath it is this",
        "project's own. `docs/39-soc-bus-and-memory-map.md` section 3 is the",
        "decision and section 7 states the claim this project does and does",
        "not make.",
        "",
        f"Vendor code `0x{meta['vendor_id']:02X}` is GRLIB's \"various",
        "contributions\" bucket. The device IDs under it are assigned by this",
        "project and are **not** registered with Frontgrade Gaisler, so a",
        "GRLIB-aware tool will show a known vendor and an unrecognised",
        "device. That is the truthful outcome; using Gaisler's own `0x01`",
        "would not be.",
        "",
        "**One field cannot express this map exactly.** An AHB-style bank",
        "address register compares `addr[31:20]`, so its granularity is",
        "1 MiB. These regions are smaller and their `mask` field is rounded",
        "up to 1 MiB:",
        "",
    ]
    for r in sorted(inexact, key=lambda x: x["base"]):
        lines.append(f"- {r['name']}, {human_size(r['size'])} at "
                     f"`0x{r['base']:08X}`")
    lines += [
        "",
        "The exact byte size of every region is therefore carried in",
        "user-defined word 1 of its record, which GRLIB leaves free, and the",
        "region's `implemented`/`reserved` status in user-defined word 2. A",
        "reader that trusts only the bank address register will over-state",
        "three region sizes; a reader that uses word 1 will not.",
        "",
    ]
    return "\n".join(lines) + "\n"


def human_size(n):
    for unit, div in (("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n >= div and n % div == 0:
            return f"{n // div} {unit}"
    return f"{n} B"


def gen_python(spec):
    meta = spec["meta"]
    apb = by_name(spec["regions"], "APB")
    lines = [f'"""{HEADER}"""', ""]
    lines.append(f'VERSION = "{meta["version"]}"')
    lines.append(f"VENDOR_ID = 0x{meta['vendor_id']:02X}")
    lines.append(f"BOOT_ADDR = 0x{by_name(spec['regions'], meta['boot_region'])['base']:08X}")
    lines.append(f"RESET_VECTOR = 0x{reset_vector(spec):08X}")
    lines.append(f"BASE_ALIGNMENT = 0x{meta['base_alignment']:X}")
    lines += ["", "# name -> (base, size, type, attr, status, port or None)",
              "REGIONS = {"]
    for r in sorted(spec["regions"], key=lambda x: x["base"]):
        port = f'"{r["port"]}"' if "port" in r else "None"
        lines.append(
            f'    "{r["name"]}": (0x{r["base"]:08X}, 0x{r["size"]:08X}, '
            f'"{r["type"]}", "{r["attr"]}", "{r["status"]}", {port}),')
    lines += ["}", "", "# name -> prefix-compare mask; addr & MASK == base", "MASKS = {"]
    for r in sorted(spec["regions"], key=lambda x: x["base"]):
        lines.append(f'    "{r["name"]}": 0x{region_mask(r):08X},')
    lines += ["}", "", "# fabric port name -> region name", "PORTS = {"]
    for r in sorted(spec["regions"], key=lambda x: x["base"]):
        if "port" in r:
            lines.append(f'    "{r["port"]}": "{r["name"]}",')
    lines += ["}", "",
              f"APB_BASE = 0x{apb['base']:08X}",
              f"APB_SIZE = 0x{apb['size']:08X}",
              "APB_SLOT_SIZE = 0x1000", "",
              "# name -> (address, slot index, irq, status)", "APB_SLOTS = {"]
    for s in sorted(spec["apb_slots"], key=lambda x: x["slot"]):
        lines.append(
            f'    "{s["name"]}": (0x{apb_addr(spec, s):08X}, 0x{s["slot"]:03X}, '
            f'{s["irq"]}, "{s["status"]}"),')
    lines += ["}", "", "# word index within the device table -> value",
              "PNP_ROM = {"]
    for w, v in sorted(pnp_words(spec).items()):
        lines.append(f"    0x{w:03X}: 0x{v:08X},")
    lines += ["}", "",
              "# word index within the peripheral device table -> value",
              "APB_PNP_ROM = {"]
    for w, v in sorted(apb_pnp_words(spec).items()):
        lines.append(f"    0x{w:03X}: 0x{v:08X},")
    lines += ["}", ""]
    return "\n".join(lines)


def gen_verilog(spec):
    meta = spec["meta"]
    apb = by_name(spec["regions"], "APB")
    lines = [
        f"// {HEADER}",
        "//",
        "// Address constants for the system fabric. BASE/MASK are a",
        "// prefix-compare pair: the region is selected when",
        "// (addr & MASK) == BASE. That is a correct decode only because",
        "// every region is a naturally aligned power of two, which the",
        "// generator enforces and sw/tests/test_memmap.py re-checks.",
        "//",
        "// DELIBERATELY NOT GUARDED with `ifndef. This file is a BODY of",
        "// localparam declarations, included inside a module, and more",
        "// than one module needs it. Verilog macro state is shared across",
        "// every file in a compilation unit, so an include guard here",
        "// would let the first module that includes it get the constants",
        "// and silently give every later module an empty file. That is",
        "// exactly what happened once: soc_top.v got the map and",
        "// soc_bus.v got nothing, and the failure was an unbound-name",
        "// error inside the address decoder with no hint of the cause.",
        "",
        f"localparam [31:0] SOC_BOOT_ADDR    = 32'h{by_name(spec['regions'], meta['boot_region'])['base']:08X};",
        f"localparam [31:0] SOC_RESET_VECTOR = 32'h{reset_vector(spec):08X};",
        "",
    ]
    for r in sorted(spec["regions"], key=lambda x: x["base"]):
        n = r["name"]
        lines.append(f"localparam [31:0] SOC_BASE_{n:<8s} = 32'h{r['base']:08X};")
        lines.append(f"localparam [31:0] SOC_SIZE_{n:<8s} = 32'h{r['size']:08X};")
        lines.append(f"localparam [31:0] SOC_MASK_{n:<8s} = 32'h{region_mask(r):08X};")
    lines += ["",
              f"localparam [31:0] SOC_APB_BASE = 32'h{apb['base']:08X};",
              "// APB slot index, compared against PADDR[19:12].",
              ]
    for s in sorted(spec["apb_slots"], key=lambda x: x["slot"]):
        lines.append(f"localparam [7:0] SOC_APBSLOT_{s['name']:<8s} = 8'h{s['slot'] & 0xFF:02X};")
    lines += ["", ""]
    return "\n".join(lines)


def gen_pnp_rom(spec):
    """The device table contents as a Verilog case body.

    Emitted as a case rather than a memory initialisation because the
    table is sparse -- about 100 non-zero words in 1024 -- and a case
    with a zero default synthesises to the constant multiplexer it is,
    with no storage.
    """
    lines = [
        f"// {HEADER}",
        "//",
        "// Body of the device table read multiplexer, textually included",
        "// inside soc_pnp.v. `word_addr` is addr[11:2]. Not guarded with",
        "// `ifndef: it is a case body, not a header, and a guard on a",
        "// body include is a trap in a shared macro namespace.",
        "",
        "case (word_addr)",
    ]
    words = pnp_words(spec)
    apb_words = apb_pnp_words(spec)
    lines.append("  // ---- master records ----")
    for w, v in sorted(words.items()):
        if w < PNP_SLAVE_BASE_WORD:
            lines.append(f"  10'h{w:03X}: pnp_data = 32'h{v:08X};")
    lines.append("  // ---- slave records ----")
    for w, v in sorted(words.items()):
        if PNP_SLAVE_BASE_WORD <= w < 0x3FC:
            lines.append(f"  10'h{w:03X}: pnp_data = 32'h{v:08X};")
    lines.append("  // ---- identity and endianness ----")
    for w, v in sorted(words.items()):
        if w >= 0x3FC:
            lines.append(f"  10'h{w:03X}: pnp_data = 32'h{v:08X};")
    lines += ["  default: pnp_data = 32'h0000_0000;", "endcase", ""]
    # The peripheral-bus table is a separate include, consumed by the
    # bridge's own table slot.
    lines.insert(0, "")
    body = "\n".join(lines)

    apb_lines = [
        "",
        "// Peripheral bus device table, two words per slot. `word_addr` is",
        "// PADDR[11:2] inside the table's own 4 KiB slot. Not guarded,",
        "// for the same reason soc_pnp_rom.vh is not.",
        "",
        "case (word_addr)",
    ]
    for w, v in sorted(apb_words.items()):
        apb_lines.append(f"  10'h{w:03X}: apb_pnp_data = 32'h{v:08X};")
    apb_lines += ["  default: apb_pnp_data = 32'h0000_0000;", "endcase", ""]
    return body, "\n".join(apb_lines)


def gen_c_header(spec):
    meta = spec["meta"]
    apb = by_name(spec["regions"], "APB")
    lines = [
        f"/* {HEADER} */",
        "#ifndef SOC_MEMMAP_H",
        "#define SOC_MEMMAP_H",
        "",
        f"#define SOC_MEMMAP_VERSION \"{meta['version']}\"",
        f"#define SOC_VENDOR_ID    0x{meta['vendor_id']:02X}u",
        f"#define SOC_BOOT_ADDR    0x{by_name(spec['regions'], meta['boot_region'])['base']:08X}u",
        f"#define SOC_RESET_VECTOR 0x{reset_vector(spec):08X}u",
        "",
    ]
    for r in sorted(spec["regions"], key=lambda x: x["base"]):
        lines.append(f"#define SOC_{r['name']}_BASE 0x{r['base']:08X}u")
        lines.append(f"#define SOC_{r['name']}_SIZE 0x{r['size']:08X}u")
    lines.append("")
    for s in sorted(spec["apb_slots"], key=lambda x: x["slot"]):
        lines.append(f"#define SOC_{s['name']}_BASE 0x{apb_addr(spec, s):08X}u")
    lines += ["", f"#define SOC_APB_BASE 0x{apb['base']:08X}u", ""]
    lines += [
        "/* Device table words the program checks. Both are generated from",
        "   the same source as the ROM contents, so a table that drifts from",
        "   the map fails in simulation rather than in a driver. */",
        f"#define SOC_PNP_IDENT_WORD  0x{pnp_words(spec)[0x3FC]:08X}u",
        f"#define SOC_PNP_ENDIAN_WORD 0x{pnp_words(spec)[0x3FD]:08X}u",
        f"#define SOC_PNP_IDENT_OFF   0x{0x3FC * 4:03X}u",
        f"#define SOC_PNP_ENDIAN_OFF  0x{0x3FD * 4:03X}u",
        "",
        "#endif /* SOC_MEMMAP_H */",
        "",
    ]
    return "\n".join(lines)


def gen_linker(spec):
    meta = spec["meta"]
    boot = by_name(spec["regions"], meta["boot_region"])
    ram = by_name(spec["regions"], "RAM")
    off = meta["reset_vector_offset"]
    return "\n".join([
        f"/* {HEADER} */",
        "",
        "/* The ROM region starts AT the reset vector, not at the region",
        "   base. Ibex resets to {boot_addr_i[31:8], 8'h80}, so the first",
        "   fetched instruction is at base+0x80 and nothing may be linked",
        "   below it -- docs/38-ibex-bringup.md section 7.5 defect 4, where",
        "   exactly that moved _start off the reset vector and the core ran",
        "   the program from arbitrary offsets. Expressing the offset here,",
        "   in generated text, is what stops the next link script from",
        "   getting it wrong. */",
        "MEMORY {",
        f"  rom (rx)  : ORIGIN = 0x{boot['base'] + off:08X}, "
        f"LENGTH = 0x{boot['size'] - off:X}",
        f"  ram (rwx) : ORIGIN = 0x{ram['base']:08X}, LENGTH = 0x{ram['size']:X}",
        "}",
        "",
        f"__soc_reset_vector = 0x{reset_vector(spec):08X};",
        f"__soc_ram_base     = 0x{ram['base']:08X};",
        f"__soc_ram_top      = 0x{ram['base'] + ram['size']:08X};",
        "",
    ])


def main():
    spec = load()
    pnp_body, apb_pnp_body = gen_pnp_rom(spec)
    outputs = {
        ROOT / "docs" / "memmap-soc.md": gen_markdown(spec),
        ROOT / "sw" / "golden" / "memmap_gen.py": gen_python(spec),
        ROOT / "hw" / "soc" / "rtl" / "soc_memmap.vh": gen_verilog(spec),
        ROOT / "hw" / "soc" / "rtl" / "soc_pnp_rom.vh": pnp_body,
        ROOT / "hw" / "soc" / "rtl" / "soc_apb_pnp_rom.vh": apb_pnp_body,
        ROOT / "hw" / "soc" / "tb" / "sw" / "soc_memmap.h": gen_c_header(spec),
        ROOT / "hw" / "soc" / "tb" / "sw" / "memmap.ld": gen_linker(spec),
    }
    check = "--check" in sys.argv
    stale = []
    for path, content in outputs.items():
        if check:
            if not path.exists() or path.read_text() != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"wrote {path.relative_to(ROOT)}")
    if check and stale:
        sys.exit("stale generated files: " + ", ".join(stale))


if __name__ == "__main__":
    main()
