"""Register map generator for the NPU configuration/status block.

Reads regmap/regmap.yaml (the single source) and emits:
  - docs/regmap-npu.md        documentation table
  - sw/golden/regmap_gen.py   Python constants for golden model / test hosts
  - hw/rtl/npu_regs.vh        Verilog localparams for the RTL

Run from anywhere:  python regmap/generate.py
The sync test (sw/tests/test_regmap.py) fails if the generated files are
stale, so regeneration is enforced by CI rather than by memory.
"""

import re
import sys
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "regmap" / "regmap.yaml"

HEADER = "GENERATED FILE - edit regmap/regmap.yaml and run regmap/generate.py"


def load():
    spec = yaml.safe_load(SRC.read_text())
    regs = []
    for block in spec["blocks"]:
        for reg in block["registers"]:
            reg["block"] = block["name"]
            regs.append(reg)
    validate(spec, regs)
    return spec, regs


def validate(spec, regs):
    meta = spec["meta"]
    addr_max = 1 << meta["addr_bits"]
    word_bytes = meta["data_bits"] // 8
    seen_offsets = {}
    seen_names = set()
    for reg in regs:
        off, name = reg["offset"], reg["name"]
        for n in [name] + [f["name"] for f in reg.get("fields", [])]:
            # catches e.g. a bare OFF parsed as a YAML 1.1 boolean
            if not (isinstance(n, str) and NAME_RE.match(n)):
                sys.exit(f"error: invalid name {n!r} (quote YAML booleans like OFF/ON)")
        if not 0 <= off < addr_max:
            sys.exit(f"error: {name} offset 0x{off:03X} outside {meta['addr_bits']}-bit space")
        if off % word_bytes:
            sys.exit(f"error: {name} offset 0x{off:03X} not {word_bytes}-byte aligned")
        if off in seen_offsets:
            sys.exit(f"error: {name} and {seen_offsets[off]} share offset 0x{off:03X}")
        if name in seen_names:
            sys.exit(f"error: duplicate register name {name}")
        seen_offsets[off] = name
        seen_names.add(name)
        if not 0 <= reg["reset"] < (1 << meta["data_bits"]):
            sys.exit(f"error: {name} reset value wider than {meta['data_bits']} bits")
        used = 0
        for field in reg.get("fields", []):
            lsb, width = field["bit"], field.get("width", 1)
            if lsb < 0 or width < 1 or lsb + width > meta["data_bits"]:
                sys.exit(f"error: {name}.{field['name']} bits [{lsb + width - 1}:{lsb}] out of range")
            mask = ((1 << width) - 1) << lsb
            if used & mask:
                sys.exit(f"error: {name}.{field['name']} overlaps another field")
            used |= mask


def field_bits(field):
    lsb, width = field["bit"], field.get("width", 1)
    return str(lsb) if width == 1 else f"{lsb + width - 1}:{lsb}"


def gen_markdown(spec, regs):
    meta = spec["meta"]
    lines = [
        "# NPU register map v" + meta["version"],
        "",
        f"<!-- {HEADER} -->",
        "",
        f"Bus: {meta['bus']}. Address space: {meta['addr_bits']}-bit byte",
        f"offsets within the block window; registers are {meta['data_bits']}-bit,",
        "word-aligned. Access codes: RO read-only, RW read-write, WO write-only,",
        "W1C write-1-to-clear, SC self-clearing.",
        "",
        "Normative register list: docs/10-npu-mvp-spec.md section 10; the",
        "sync test (sw/tests/test_regmap.py) enforces the alignment.",
        "",
    ]
    for block in spec["blocks"]:
        lines += [f"## {block['name']} - {block['desc']}", "",
                  "| Offset | Name | Access | Reset | Description |",
                  "|---|---|---|---|---|"]
        for reg in block["registers"]:
            lines.append(
                f"| 0x{reg['offset']:03X} | {reg['name']} | {reg['access']} "
                f"| 0x{reg['reset']:08X} | {reg['desc']} |")
        for reg in block["registers"]:
            if reg.get("fields"):
                lines += ["", f"### {reg['name']} fields", "",
                          "| Bits | Field | Access | Description |",
                          "|---|---|---|---|"]
                for f in reg["fields"]:
                    lines.append(f"| {field_bits(f)} | {f['name']} | {f['access']} | {f['desc']} |")
        lines.append("")
    return "\n".join(lines)


def gen_python(spec, regs):
    lines = [f'"""{HEADER}"""', "", "ADDR = {"]
    for reg in regs:
        lines.append(f'    "{reg["name"]}": 0x{reg["offset"]:03X},')
    lines += ["}", "", "ACCESS = {"]
    for reg in regs:
        lines.append(f'    "{reg["name"]}": "{reg["access"]}",')
    lines += ["}", "", "RESET = {"]
    for reg in regs:
        lines.append(f'    "{reg["name"]}": 0x{reg["reset"]:08X},')
    lines += ["}", "", "# field name -> LSB position", "FIELDS = {"]
    for reg in regs:
        if reg.get("fields"):
            bits = ", ".join(f'"{f["name"]}": {f["bit"]}' for f in reg["fields"])
            lines.append(f'    "{reg["name"]}": {{{bits}}},')
    lines += ["}", "", "# field name -> width in bits", "FIELD_WIDTHS = {"]
    for reg in regs:
        if reg.get("fields"):
            widths = ", ".join(f'"{f["name"]}": {f.get("width", 1)}' for f in reg["fields"])
            lines.append(f'    "{reg["name"]}": {{{widths}}},')
    lines += ["}", ""]
    return "\n".join(lines)


def gen_verilog(spec, regs):
    ab = spec["meta"]["addr_bits"]
    db = spec["meta"]["data_bits"]
    lines = [f"// {HEADER}", "`ifndef NPU_REGS_VH", "`define NPU_REGS_VH", ""]
    for reg in regs:
        lines.append(f"localparam [{ab - 1}:0] ADDR_{reg['name']} = {ab}'h{reg['offset']:03X};")
    lines.append("")
    for reg in regs:
        lines.append(f"localparam [{db - 1}:0] RST_{reg['name']} = {db}'h{reg['reset']:08X};")
    lines.append("")
    for reg in regs:
        for f in reg.get("fields", []):
            lines.append(f"localparam BIT_{reg['name']}_{f['name']} = {f['bit']};")
            if f.get("width", 1) != 1:
                lines.append(f"localparam WIDTH_{reg['name']}_{f['name']} = {f['width']};")
    lines += ["", "`endif // NPU_REGS_VH", ""]
    return "\n".join(lines)


def main():
    spec, regs = load()
    outputs = {
        ROOT / "docs" / "regmap-npu.md": gen_markdown(spec, regs),
        ROOT / "sw" / "golden" / "regmap_gen.py": gen_python(spec, regs),
        ROOT / "hw" / "rtl" / "npu_regs.vh": gen_verilog(spec, regs),
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
