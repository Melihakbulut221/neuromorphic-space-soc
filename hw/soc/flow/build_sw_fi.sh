#!/usr/bin/env bash
# Build the core fault-injection workload into a boot ROM image.
#
#   build_sw_fi.sh <out_dir> [extra CPPFLAGS...]
#
# The sibling build_sw_soc.sh builds the bring-up program of docs/38 to
# docs/40 for the same platform. This builds hw/soc/tb/sw/fi_workload.c
# instead, against the SAME crt0.S and the SAME linker script, so the
# reset sequence, the vector table, the trap handler and the memory map
# are the ones the rest of the project runs and not a campaign-local
# copy. docs/42 section 2.
#
# Everything else -- the toolchain, the flags, the ROM padding, the hex
# format -- is build_sw_soc.sh's, deliberately unchanged.

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

"$GCC" \
  -march=rv32imc_zicsr_zifencei -mabi=ilp32 -mcmodel=medlow \
  -Os -g -ffreestanding -fno-builtin -nostdlib -nostartfiles \
  -Wall -Wextra -Werror \
  -DSOC_PLATFORM \
  -I "$SW" -L "$SW" \
  -T "$SW/link_soc.ld" \
  "$@" \
  "$SW/crt0.S" "$SW/fi_workload.c" \
  -o "$OUT/fi_workload.elf" -lgcc

"$OBJDUMP" -d -S "$OUT/fi_workload.elf" > "$OUT/fi_workload.dis"
"$OBJCOPY" -O binary "$OUT/fi_workload.elf" "$OUT/fi_workload.bin"

PAD_WORDS=${PAD_WORDS:-2016}
python3 - "$OUT/fi_workload.bin" "$OUT/fi_workload.hex" "$PAD_WORDS" <<'PY'
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

echo "== fi workload: $(stat -c%s "$OUT/fi_workload.bin") bytes of ROM image"
