#!/usr/bin/env bash
# Build the NPU-connection fault-injection workload into a boot ROM image.
#
#   build_sw_npu_fi.sh <out_dir> [extra CPPFLAGS...]
#
# The sibling build_sw_fi.sh builds docs/42's core kernel and
# build_sw_soc.sh builds the bring-up program. This builds
# hw/soc/tb/sw/fi_npu.c, against the SAME crt0.S and the SAME linker
# script, so the reset sequence, the vector table, the trap handler and
# the memory map are the ones the rest of the project runs and not a
# campaign-local copy. docs/52 section 2.
#
# THE ONE THING THIS SCRIPT DOES THAT build_sw_fi.sh DOES NOT is run
# hw/soc/flow/gen_npu_vectors.py first, exactly as build_sw_soc.sh does.
# That is the campaign's oracle: sw/golden/lif_core.py computes the
# expected event stream and the expected neuron state file at BUILD TIME,
# into headers the program compiles against, so the program never asks
# the hardware what the answer is. docs/52 section 5 is why that matters
# more here than anywhere else in this repository.
#
# Everything else -- the toolchain, the flags, the ROM padding, the hex
# format -- is build_sw_fi.sh's, deliberately unchanged.

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

# The golden model computes this campaign's expected answer here, before
# the program that will be checked against it is compiled. Nothing in
# this step reads any RTL or any simulation output.
python3 "$SOC_DIR/flow/gen_npu_vectors.py" "$OUT"

"$GCC" \
  -march=rv32imc_zicsr_zifencei -mabi=ilp32 -mcmodel=medlow \
  -Os -g -ffreestanding -fno-builtin -nostdlib -nostartfiles \
  -Wall -Wextra -Werror \
  -DSOC_PLATFORM \
  -I "$SW" -I "$OUT" -L "$SW" \
  -T "$SW/link_soc.ld" \
  "$@" \
  "$SW/crt0.S" "$SW/fi_npu.c" \
  -o "$OUT/fi_npu.elf" -lgcc

"$OBJDUMP" -d -S "$OUT/fi_npu.elf" > "$OUT/fi_npu.dis"
"$OBJCOPY" -O binary "$OUT/fi_npu.elf" "$OUT/fi_npu.bin"

PAD_WORDS=${PAD_WORDS:-2016}
python3 - "$OUT/fi_npu.bin" "$OUT/fi_npu.hex" "$PAD_WORDS" <<'PY'
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

echo "== npu fi workload: $(stat -c%s "$OUT/fi_npu.bin") bytes of ROM image"
