#!/usr/bin/env bash
# Build the static partitioned supervisor workload into a boot ROM image.
#
#   build_sw_sup.sh <out_dir> [extra CPPFLAGS...]
#
# The sibling build_sw_fi.sh builds hw/soc/tb/sw/fi_workload.c, the
# docs/42 campaign workload, against the shared crt0.S. This builds
# hw/soc/tb/sw/fi_supervisor.c against hw/soc/tb/sw/sup_crt0.S instead --
# a SECOND startup file, whose header says at length why it exists and
# what the duplication costs.
#
# Everything else -- the toolchain, the flags, the LINKER SCRIPT, the ROM
# padding, the hex format -- is build_sw_fi.sh's, deliberately unchanged.
# The linker script in particular is shared and is not copied, because it
# is what asserts the two Ibex constraints docs/38 section 7.5 defects 3
# and 4 cost a debugging session each: `_start` on the reset vector and
# the vector table 256-byte aligned and exactly 128 bytes.

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
  "$SW/sup_crt0.S" "$SW/fi_supervisor.c" \
  -o "$OUT/fi_supervisor.elf" -lgcc

"$OBJDUMP" -d -S "$OUT/fi_supervisor.elf" > "$OUT/fi_supervisor.dis"
"$OBJCOPY" -O binary "$OUT/fi_supervisor.elf" "$OUT/fi_supervisor.bin"

PAD_WORDS=${PAD_WORDS:-2016}
python3 - "$OUT/fi_supervisor.bin" "$OUT/fi_supervisor.hex" "$PAD_WORDS" <<'PY'
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

echo "== supervisor workload: $(stat -c%s "$OUT/fi_supervisor.bin") bytes of ROM image"
