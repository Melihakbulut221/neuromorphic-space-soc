#!/usr/bin/env bash
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
#   -I $OUT              so the two headers gen_npu_vectors.py emits
#                        into the build directory resolve: npu_regs.h,
#                        the node register map from regmap/regmap.yaml,
#                        and npu_vectors.h, this build's NPU stimulus
#                        together with the answer sw/golden computes for
#                        it. They are regenerated on EVERY build, from
#                        the golden model, so the program cannot be
#                        checking yesterday's answer.
#
# The output binary is the ROM contents: .text, .trapvec, .rodata and the
# load image of .data, in that order. .bss and the PMP buffer are NOLOAD
# and are not in it -- crt0.S zeroes the first and the second is never
# initialised.

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

"$GCC" \
  -march=rv32imc_zicsr_zifencei -mabi=ilp32 -mcmodel=medlow \
  -Os -g -ffreestanding -fno-builtin -nostdlib -nostartfiles \
  -Wall -Wextra -Werror \
  -DSOC_PLATFORM -DHAVE_PMP \
  -I "$SW" -I "$OUT" -L "$SW" \
  -T "$SW/link_soc.ld" \
  "$@" \
  "$SW/crt0.S" "$SW/test_ibex.c" \
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

echo "== sw: $(stat -c%s "$OUT/test_soc.bin") bytes of ROM image"
