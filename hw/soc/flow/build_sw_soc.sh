#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Build the self-test for the real SoC into a boot ROM image.
#
#   build_sw_soc.sh <out_dir> [extra CPPFLAGS...]
#
# The sibling build_sw.sh builds the same sources for the minimal
# testbench memory of docs/38. This one builds them for the frozen memory
# map of docs/39-soc-bus-and-memory-map.md:
#
#   -DSOC_PLATFORM       selects the SoC paths in crt0.S and test_ibex.c
#   -T link_soc.ld       .text in the boot ROM, .data relocated to RAM
#   -L $SW               so the linker script's `INCLUDE memmap.ld` finds
#                        the generated MEMORY block. That file is emitted
#                        by regmap/generate_memmap.py from
#                        regmap/memmap.yaml, so the reset vector reaches
#                        the linker from the same source that reaches the
#                        RTL and the tests.
#   -I $SW               so #include "soc_memmap.h", also generated,
#                        resolves.
#   -I $OUT              so the headers gen_npu_vectors.py and
#                        gen_flash_image.py emit into the build
#                        directory resolve: npu_regs.h,
#                        the node register map from regmap/regmap.yaml,
#                        and npu_vectors.h, this build's NPU stimulus
#                        together with the answer sw/golden computes for
#                        it. They are regenerated on EVERY build, from
#                        the golden model, so the program cannot be
#                        checking yesterday's answer.
#
# =====================================================================
# TWO PROGRAMS SINCE docs/68, AND THE ROM NO LONGER HOLDS THE BIG ONE
# =====================================================================
#
# docs/66 section 7.1 measured that the bring-up program had OUTGROWN
# the boot ROM: 7,826 of the 8,064 bytes above the reset vector, with
# the two flash checks needing 1,800 more, so the flash demonstration
# had to be a second image built from the same file with most of the
# program compiled out. docs/68 ends that. This script now builds:
#
#   app.elf       hw/soc/tb/sw/crt0.S + test_ibex.c, linked with
#                 link_app.ld so that EVERYTHING is in RAM. This is the
#                 program; it is bounded by the 32 KiB of RAM, not by
#                 the 8 KiB of ROM, and `objcopy -O binary` over it is
#                 exactly the bytes the loader copies.
#   test_soc.elf  hw/soc/tb/sw/boot_crt0.S + boot.c, linked with
#                 link_boot.ld into the ROM. This is what the boot ROM
#                 holds, and test_soc.hex -- the name every flow and
#                 testbench already knows -- is its $readmemh image.
#
# BOOT_CORRUPT selects gen_boot_image.py's counterfactual: which of the
# two image slots in the flash is broken, and how. It defaults to
# `none`, which is the design; every other value is a demonstration of
# one branch of the loader's escalation (docs/68 section 6).
#
# The ROM image is the LOADER's contents: .text, .trapvec, .rodata and
# the load image of its .data. Its .bss is NOLOAD and is not in it --
# boot_crt0.S's RAM sweep is what zeroes it, and that sweep is why there
# is no .bss loop.

set -euo pipefail

OUT=${1:?out dir}
shift || true
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SW=$SOC_DIR/tb/sw
GCC=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-gcc
OBJCOPY=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-objcopy
OBJDUMP=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-objdump

for f in "$SW/memmap.ld" "$SW/soc_memmap.h"; do
  [ -f "$f" ] || {
    echo "missing $f: run 'python regmap/generate_memmap.py' first" >&2
    exit 1; }
done

mkdir -p "$OUT"

# The golden model computes the NPU demonstration's expected answer here,
# before the program that will be checked against it is compiled. Nothing
# in this step reads any RTL or any simulation output.
python3 "$SOC_DIR/flow/gen_npu_vectors.py" "$OUT"
# And the flash images (docs/66): the pattern the program reads through
# the QSPI controller and the SAME weight words as a flash-resident
# image, with qspi_image.h carrying the expected sample words. Both
# come from the same generators as the ROM's own copies, so the two
# inferences in checks 26 and 30 are the same inference.
python3 "$SOC_DIR/flow/gen_flash_image.py" "$OUT"

CFLAGS=(-march=rv32imc_zicsr_zifencei -mabi=ilp32 -mcmodel=medlow
        -Os -g -ffreestanding -fno-builtin -nostdlib -nostartfiles
        -Wall -Wextra -Werror
        -DSOC_PLATFORM -DHAVE_PMP
        -I "$SW" -I "$OUT" -L "$SW")

# ---- 1. the application, linked to run from RAM ---------------------
# --no-warn-rwx-segments: the whole application is in one RAM region
# that the map marks rwx, so the single load segment is necessarily
# writable and executable. That is a property of a part with one RAM and
# no MMU, not of this link; the PMP is where execution permission is
# expressed on this core (test_ibex.c's HAVE_PMP checks).
"$GCC" "${CFLAGS[@]}" -Wl,--no-warn-rwx-segments -T "$SW/link_app.ld" "$@" \
  "$SW/crt0.S" "$SW/test_ibex.c" \
  -o "$OUT/app.elf" -lgcc

"$OBJDUMP" -d -S "$OUT/app.elf" > "$OUT/app.dis"
"$OBJCOPY" -O binary "$OUT/app.elf" "$OUT/app.bin"
echo "== app: $(stat -c%s "$OUT/app.bin") bytes of RAM image"

# ---- 2. the image into the flash, and the header the loader uses ----
#
# It reads the load address and the entry point OUT OF THE ELF rather
# than being told them, so a program that moved cannot be loaded to
# where it used to be. The two slots are 16 KiB apart in the modelled
# device; gen_boot_image.py says why two.
python3 "$SOC_DIR/flow/gen_boot_image.py" "$OUT" \
  --app "$OUT/app.bin" --elf "$OUT/app.elf" \
  --nm "$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-nm" \
  --corrupt "${BOOT_CORRUPT:-none}"

# ---- 3. the loader, into the boot ROM -------------------------------
"$GCC" "${CFLAGS[@]}" -T "$SW/link_boot.ld" "$@" \
  "$SW/boot_crt0.S" "$SW/boot.c" \
  -o "$OUT/test_soc.elf" -lgcc

"$OBJDUMP" -d -S "$OUT/test_soc.elf" > "$OUT/test_soc.dis"
"$OBJCOPY" -O binary "$OUT/test_soc.elf" "$OUT/test_soc.bin"

# $readmemh wants one 32-bit word per line, little-endian. soc_top.v
# hands soc_mem the INIT_WORD offset derived from the map, so this file
# holds only the part of the ROM at and above the reset vector. It is
# padded to exactly that many words so $readmemh fills the range it was
# given and does not warn -- an unpadded file works but its warning looks
# like a load failure in the log.
PAD_WORDS=${PAD_WORDS:-2016}
python3 - "$OUT/test_soc.bin" "$OUT/test_soc.hex" "$PAD_WORDS" <<'PY'
import sys, struct
raw = open(sys.argv[1], "rb").read()
raw += b"\0" * ((-len(raw)) % 4)
words = [w for (w,) in struct.iter_unpack("<I", raw)]
pad = int(sys.argv[3])
if len(words) > pad:
    sys.exit("image is %d words, does not fit in the %d-word ROM aperture"
             % (len(words), pad))
words += [0] * (pad - len(words))
with open(sys.argv[2], "w") as f:
    for w in words:
        f.write("%08x\n" % w)
PY

echo "== sw: $(stat -c%s "$OUT/test_soc.bin") bytes of ROM image (the loader)"
