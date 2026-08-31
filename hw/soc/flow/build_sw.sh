#!/usr/bin/env bash
# Build the Ibex bring-up self-test into a $readmemh image.
#
#   build_sw.sh <out_dir> [extra CPPFLAGS...]
#
# Toolchain: xPack riscv-none-elf-gcc, pinned in tools.soc.mk by release
# tag and sha256. -march=rv32imc_zicsr_zifencei -mabi=ilp32 matches the core
# configuration exactly (BaseIsaRV32I + RV32MFast + RV32Zca); building
# for anything wider would test the assembler, not the core.
#
# -Os and -ffreestanding, no libc, no libgcc division helpers: the M
# extension has to be exercised by real mul/div instructions, so
# -mno-div would defeat the point.

set -euo pipefail

OUT=${1:?out dir}
shift || true
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SW=$SOC_DIR/tb/sw
GCC=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-gcc
OBJCOPY=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-objcopy
OBJDUMP=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-objdump

mkdir -p "$OUT"

"$GCC" \
  -march=rv32imc_zicsr_zifencei -mabi=ilp32 -mcmodel=medlow \
  -Os -g -ffreestanding -fno-builtin -nostdlib -nostartfiles \
  -Wall -Wextra -Werror \
  -T "$SW/link.ld" \
  "$@" \
  "$SW/crt0.S" "$SW/test_ibex.c" \
  -o "$OUT/test_ibex.elf" -lgcc

"$OBJDUMP" -d -S "$OUT/test_ibex.elf" > "$OUT/test_ibex.dis"
"$OBJCOPY" -O binary "$OUT/test_ibex.elf" "$OUT/test_ibex.bin"

# $readmemh wants one 32-bit word per line, little-endian, starting at
# the reset vector. The image is placed at 0x80, and the testbench loads
# it at word index 0x80/4 = 32, so the file holds only the loaded part.
# The image is padded to exactly the number of words the testbench's
# RAM has above the reset vector (MEM_WORDS - 0x80/4 = 4096 - 32), so
# $readmemh fills the whole requested range and does not warn. An
# unpadded file works too, but the warning it produces looks like a load
# failure in the log and this run has to be readable at a glance.
python3 - "$OUT/test_ibex.bin" "$OUT/test_ibex.hex" "${PAD_WORDS:-4064}" <<'PY'
import sys, struct
raw = open(sys.argv[1], "rb").read()
raw += b"\0" * ((-len(raw)) % 4)
words = [w for (w,) in struct.iter_unpack("<I", raw)]
pad = int(sys.argv[3])
if len(words) > pad:
    sys.exit("image is %d words, does not fit in %d" % (len(words), pad))
words += [0] * (pad - len(words))
with open(sys.argv[2], "w") as f:
    for w in words:
        f.write("%08x\n" % w)
PY

echo "== sw: $(wc -l < "$OUT/test_ibex.hex") words ($(stat -c%s "$OUT/test_ibex.bin") bytes)"
