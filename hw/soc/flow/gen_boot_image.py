#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Put the application image into the flash the boot loader reads, and
emit the header the loader is compiled against.

WHY THIS IS A SECOND SCRIPT AND NOT PART OF gen_flash_image.py.
gen_flash_image.py runs BEFORE anything is compiled: it writes the byte
pattern docs/66's checks read and the NPU weight image, neither of which
depends on a program. This one runs AFTER the application has been
linked, because what it writes into the flash is the application, and
what it takes out of the ELF -- the load address, the entry point and
the length -- it takes out of the ELF rather than being told, so a
program that moved cannot be loaded to where it used to be.

Two slots, and they are the loader's redundancy (docs/68 section 6):

    BOOT_IMG0_OFF   the primary image
    BOOT_IMG1_OFF   the secondary, byte for byte the same image

GR716B validates an application image "optionally from redundant
memories" (docs/08 section 2.4). Two copies in one device is the weakest
form of that -- it survives a corrupted sector and not a dead part --
and it is what a part with one flash and two chip selects can offer
without a second device on the board. The offsets are 16 KiB apart, so
the two copies never share a 4 KiB sector or a 64 KiB block of the
W25Q128JV.

THE HEADER IS EIGHT WORDS AND IT SUMS TO ZERO. hw/soc/tb/sw/soc_boot.h
declares the layout and this script is the only thing that writes it;
the loader checks the magic first, then that the eight words sum to
zero, then the geometry, then the body's checksum -- and it computes
that last one by READING THE RAM BACK, not from what the flash
delivered. docs/68 section 5.

The --corrupt knob is the counterfactual generator. Each mode breaks one
thing and nothing else, so the loader's report of WHICH check failed is
checkable against what was actually broken:

    none        both images good
    magic0      the primary's magic word
    hdr0        the primary's header checksum
    geom0       the primary's load address, pushed into the loader's own
                private RAM -- the check that stops an image destroying
                the loader that is copying it
    csum0       one body word of the primary
    both        the primary's magic and the secondary's body checksum
    all         both images' magic words: nothing bootable in the device

Run:  python3 hw/soc/flow/gen_boot_image.py <out_dir> --app <app.bin> \\
              --elf <app.elf> [--corrupt MODE]
"""

import argparse
import struct
import subprocess
import sys
from pathlib import Path

# The two slots, in the 128 KiB the modelled device holds. They sit
# above gen_flash_image.py's pattern (0x00000000..0x00008000) and its
# weight image (0x00010000), and 16 KiB apart from each other.
BOOT_IMG0_OFF = 0x018000
BOOT_IMG1_OFF = 0x01C000
BOOT_SLOT_BYTES = 0x004000

MAGIC = 0x3142534E              # "NSB1" little-endian
HDR_WORDS = 8


def elf_symbols(elf, nm):
    out = subprocess.run([nm, str(elf)], capture_output=True, text=True,
                         check=True).stdout
    syms = {}
    for line in out.splitlines():
        f = line.split()
        if len(f) == 3:
            syms[f[2]] = int(f[0], 16)
    return syms


def make_header(load, nbytes, entry, csum, version):
    """Eight words whose sum is zero modulo 2^32."""
    w = [MAGIC, load, nbytes, entry, csum, version, 0, 0]
    w[7] = (-sum(w[:7])) & 0xFFFFFFFF
    assert sum(w) % (1 << 32) == 0
    return w


def body_checksum(body):
    s = 0
    for (v,) in struct.iter_unpack("<I", body):
        s = (s + v) & 0xFFFFFFFF
    return s


def build_slot(body, load, entry, version, corrupt):
    """One slot's bytes: header then body, with `corrupt` applied.

    THE CHECKSUM IS TAKEN BEFORE THE BODY IS CORRUPTED, and the order is
    the whole point of the `csum` mode. The first version took it
    afterwards, which produced a perfectly consistent image OF A
    CORRUPTED PROGRAM: the loader accepted it, jumped into an
    instruction with a bit flipped, and the run hung instead of
    demonstrating a checksum mismatch. A mutation that does not apply is
    the shape docs/41 section 6.6 counts; this one applied, to the wrong
    thing.
    """
    b = bytearray(body)
    csum = body_checksum(bytes(b))
    if corrupt == "csum":
        b[0] ^= 0x01            # one bit of one body word, after the sum
    hdr = make_header(load, len(b), entry, csum, version)
    if corrupt == "magic":
        hdr[0] ^= 0xFF
    elif corrupt == "hdr":
        hdr[5] ^= 0x01          # the version word; the sum no longer zero
    elif corrupt == "geom":
        # An image that claims to load over the top of RAM, which is
        # where the loader's own stack is. The header still checks.
        hdr = make_header(0x7F00, len(b), 0x7F00, csum, version)
    return struct.pack("<8I", *hdr) + bytes(b)


CORRUPT = {
    "none":   (None, None),
    "magic0": ("magic", None),
    "hdr0":   ("hdr", None),
    "geom0":  ("geom", None),
    "csum0":  ("csum", None),
    "both":   ("magic", "csum"),
    "all":    ("magic", "magic"),
}


def emit_header(out, load, entry, nbytes, version, mode):
    L = []
    L.append("/* GENERATED by hw/soc/flow/gen_boot_image.py. Do not edit. */")
    L.append("/*")
    L.append(" * Where the boot loader looks for an image, and what this")
    L.append(" * build put there. The OFFSETS are what hw/soc/tb/sw/boot.c is")
    L.append(" * compiled against; everything below them is reported so that")
    L.append(" * a log can be read against the build that produced it, and")
    L.append(" * the loader reads none of it -- it takes the load address,")
    L.append(" * the length and the entry point out of the image's own")
    L.append(" * header, which is the only way a loader in a mask ROM can")
    L.append(" * work.")
    L.append(" */")
    L.append("#ifndef BOOT_IMAGE_H")
    L.append("#define BOOT_IMAGE_H")
    L.append("")
    L.append(f"#define BOOT_IMG0_OFF 0x{BOOT_IMG0_OFF:06X}u")
    L.append(f"#define BOOT_IMG1_OFF 0x{BOOT_IMG1_OFF:06X}u")
    L.append(f"#define BOOT_SLOT_BYTES 0x{BOOT_SLOT_BYTES:06X}u")
    L.append("")
    L.append("/* This build, for the log's benefit only. */")
    L.append(f"#define BOOT_BUILD_LOAD  0x{load:08X}u")
    L.append(f"#define BOOT_BUILD_ENTRY 0x{entry:08X}u")
    L.append(f"#define BOOT_BUILD_BYTES {nbytes}u")
    L.append(f"#define BOOT_BUILD_VER   0x{version:08X}u")
    L.append(f'#define BOOT_BUILD_CORRUPT "{mode}"')
    L.append("")
    L.append("#endif /* BOOT_IMAGE_H */")
    L.append("")
    out.write_text("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--app", required=True)
    ap.add_argument("--elf", required=True)
    ap.add_argument("--nm", required=True)
    ap.add_argument("--corrupt", default="none", choices=sorted(CORRUPT))
    ap.add_argument("--version", type=lambda s: int(s, 0), default=0x00680001)
    a = ap.parse_args()

    out = Path(a.out)
    body = Path(a.app).read_bytes()
    body += b"\0" * ((-len(body)) % 4)

    syms = elf_symbols(Path(a.elf), a.nm)
    for need in ("_start", "__soc_ram_base"):
        if need not in syms:
            sys.exit(f"gen_boot_image: {need} is not in {a.elf}")
    load = syms["__soc_ram_base"]
    entry = syms["_start"]
    if entry != load:
        sys.exit("gen_boot_image: the application's _start is not at the "
                 "base of RAM; link_app.ld's ASSERT should have caught this")
    if len(body) > BOOT_SLOT_BYTES - HDR_WORDS * 4:
        sys.exit(f"gen_boot_image: the image is {len(body)} bytes and a slot "
                 f"holds {BOOT_SLOT_BYTES - HDR_WORDS * 4}")

    c0, c1 = CORRUPT[a.corrupt]
    slot0 = build_slot(body, load, entry, a.version, c0)
    slot1 = build_slot(body, load, entry, a.version, c1)

    # Rewrite the flash image gen_flash_image.py already wrote, in
    # place: it is a byte-per-line $readmemh file and the two slots are
    # a contiguous range of lines each.
    hexpath = out / "flash0.hex"
    if not hexpath.is_file():
        sys.exit(f"gen_boot_image: {hexpath} does not exist; "
                 "gen_flash_image.py runs first")
    lines = hexpath.read_text().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for off, blob in ((BOOT_IMG0_OFF, slot0), (BOOT_IMG1_OFF, slot1)):
        if off + len(blob) > len(lines):
            sys.exit("gen_boot_image: the image does not fit in the "
                     "modelled device")
        for i, byte in enumerate(blob):
            lines[off + i] = "%02x" % byte
    hexpath.write_text("\n".join(lines) + "\n")

    emit_header(out / "boot_image.h", load, entry, len(body), a.version,
                a.corrupt)
    print(f"wrote {hexpath} slots 0x{BOOT_IMG0_OFF:06X} and "
          f"0x{BOOT_IMG1_OFF:06X}: {len(body)} bytes at 0x{load:08X}, "
          f"entry 0x{entry:08X}, corrupt={a.corrupt}")


if __name__ == "__main__":
    main()
