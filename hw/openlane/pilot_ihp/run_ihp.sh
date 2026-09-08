#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

#
# IHP SG13G2 corner-experiment hardening of the 4x2 pilot, rootless.
#
# The docs/20 section 5 companion to hw/openlane/pilot_sky130/run_sky130.sh.
# It hardens the same module, at the same 4x2 tile geometry, from the
# same configuration the Tiny Tapeout GDS action would use -- see
# mkconfig.py, which derives config.json mechanically from
# tt/src/config_merged.json -- with PNR_CORNERS as the only variable
# under test.
#
# Why this is not `run_trial.sh --design pilot_ihp`. run_trial.sh does
# exactly the right thing for a single config per design directory, but
# it resolves CONFIG to "$DESIGN/config.json" with no override, and this
# experiment needs to run a baseline and a variant out of the same
# directory so that every `dir::` path resolves identically for both.
# run_trial.sh is docs/12's and is left untouched; the toolchain
# discipline below -- the shim set, the venv, the unset LD_LIBRARY_PATH,
# the LibreLane-pinned PDK assertion -- is copied from it verbatim and
# the rationale for each line is in docs/12 sections 2.1 and 2.4b.
#
# Usage:
#   hw/openlane/pilot_ihp/run_ihp.sh --run-tag ihp-baseline
#   CONFIG=$PWD/hw/openlane/pilot_ihp/config.pnrcorners.json \
#     hw/openlane/pilot_ihp/run_ihp.sh --run-tag ihp-pnrcorners
#   ENABLE_PDK=1 hw/openlane/pilot_ihp/run_ihp.sh
#
# Environment overrides: CONFIG, SHIMS, VENV, OSS_CAD, PDK_ROOT.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="${CONFIG:-$HERE/config.json}"
[ -f "$CONFIG" ] || { echo "no config at $CONFIG"; exit 1; }

SHIMS="${SHIMS:-$HOME/.local/opt/llbin}"
VENV="${VENV:-$HOME/Documents/caravel-lif-crossbar/.venv-flow}"
OSS_CAD="${OSS_CAD:-$HOME/Documents/gt2n-soc/tools/oss-cad-suite/bin}"
export PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"

PDK=ihp-sg13g2
SCL=sg13g2_stdcell

[ -x "$SHIMS/openroad" ]     || { echo "missing shims at $SHIMS"; exit 1; }
[ -x "$VENV/bin/librelane" ] || { echo "missing librelane venv at $VENV"; exit 1; }
[ -x "$VENV/bin/ciel" ]      || { echo "missing ciel in $VENV"; exit 1; }

export PATH="$SHIMS:$VENV/bin:$OSS_CAD:$PATH"
# Deliberate: the shims set LD_LIBRARY_PATH themselves, per tool. An
# inherited value here would apply the OpenROAD glibc to every process.
unset LD_LIBRARY_PATH

# The PDK version is pinned by LibreLane, not by us. Read the pin out of
# the installed wheel so this stays correct across LibreLane upgrades
# instead of hard-coding a hash that goes stale silently.
PIN="$("$VENV/bin/python" - "$PDK" <<'PY'
import sys, importlib.util, os, re
spec = importlib.util.find_spec("librelane")
path = os.path.join(os.path.dirname(spec.origin), "pdk_hashes.yaml")
want = sys.argv[1]
for line in open(path):
    m = re.match(r"\s*([\w.-]+)\s*:\s*(\S+)", line)
    if m and m.group(1) == want:
        print(m.group(2))
        break
PY
)"
[ -n "$PIN" ] || { echo "no $PDK pin in this LibreLane's pdk_hashes.yaml"; exit 1; }

# readlink -e (not -f) on purpose: -f canonicalises a path whose last
# component does not exist, so with no PDK enabled at all it would report
# basename(PDK_ROOT) as the enabled version and the <none> branch below
# could never be taken.
ENABLED=""
if TARGET="$(readlink -e "$PDK_ROOT/$PDK" 2>/dev/null)"; then
    ENABLED="$(basename "$(dirname "$TARGET")")"
fi
if [ "$ENABLED" != "$PIN" ]; then
    if [ "${ENABLE_PDK:-0}" = 1 ]; then
        ciel enable --pdk-family "$PDK" "$PIN"
    else
        echo "PDK version mismatch."
        echo "  enabled: ${ENABLED:-<none>}"
        echo "  pinned:  $PIN  (librelane $("$VENV/bin/librelane" --version | head -1 | awk '{print $2}'))"
        echo "Fix with: ciel enable --pdk-family $PDK $PIN"
        echo "      or: ENABLE_PDK=1 $0"
        exit 1
    fi
fi

exec librelane --pdk "$PDK" --scl "$SCL" "$@" "$CONFIG"
