#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

#
# SKY130A hardening of the 4x2 pilot through LibreLane, rootless.
#
# The cross-PDK portability run of docs/18. Same design and same clock
# constraint as the ihp-sg13g2 4x2 harden of docs/15 section 5.3; the
# only variables are the PDK, the standard-cell library, the tile
# geometry and the pin-frame DEF.
#
# This is a copy of hw/openlane/run_trial.sh with the PDK/SCL pair
# changed and the pin-assertion rewritten for the sky130 family, rather
# than a --pdk flag added to that script: run_trial.sh is owned by
# docs/12 and this workstream does not modify it. Everything else --
# the shim set, the venv, the LD_LIBRARY_PATH discipline, the
# LibreLane-pinned PDK version assertion -- is unchanged and the
# rationale for each is in docs/12 sections 2.1 and 2.4b.
#
# Usage:
#   hw/openlane/pilot_sky130/run_sky130.sh                 # full flow
#   hw/openlane/pilot_sky130/run_sky130.sh -T Yosys.Synthesis
#   ENABLE_PDK=1 hw/openlane/pilot_sky130/run_sky130.sh    # switch ciel to the pin
#   CONFIG=$PWD/config.pnrcorners.json ...run_sky130.sh    # a generated variant
#
# Environment overrides: CONFIG, SHIMS, VENV, OSS_CAD, PDK_ROOT.
#
# CONFIG exists for the docs/20 corner experiments. A variant is a copy
# of config.json with a small, named key delta, written into THIS
# directory by mkvariant.py -- same directory because every `dir::` path
# in the config resolves relative to the config file, so a variant kept
# anywhere else would silently point at different sources or a different
# pin-frame DEF. Generated rather than hand-copied so the delta against
# the baseline is the only thing that can differ.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="${CONFIG:-$HERE/config.json}"
[ -f "$CONFIG" ] || { echo "no config at $CONFIG"; exit 1; }

SHIMS="${SHIMS:-$HOME/.local/opt/llbin}"
VENV="${VENV:-$HOME/Documents/caravel-lif-crossbar/.venv-flow}"
OSS_CAD="${OSS_CAD:-$HOME/Documents/gt2n-soc/tools/oss-cad-suite/bin}"
export PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"

# sky130A is a variant of the sky130 ciel FAMILY. ciel enable/ls-remote
# take the family; PDK_ROOT carries one symlink per variant (sky130A and
# sky130B) into the same version directory. LibreLane's --pdk takes the
# variant. The two names are not interchangeable on the command line.
PDK_FAMILY=sky130
PDK=sky130A
SCL=sky130_fd_sc_hd

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
PIN="$("$VENV/bin/python" - "$PDK_FAMILY" <<'PY'
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
[ -n "$PIN" ] || { echo "no $PDK_FAMILY pin in this LibreLane's pdk_hashes.yaml"; exit 1; }

# $PDK_ROOT/<variant> -> ciel/<family>/versions/<hash>/<variant>, so the
# version is the parent directory of the resolved link target. readlink -e
# (not -f) on purpose: -f canonicalises a path whose last component does
# not exist, so with no PDK enabled at all it would report
# basename(PDK_ROOT) as the enabled version and the <none> branch below
# could never be taken.
ENABLED=""
if TARGET="$(readlink -e "$PDK_ROOT/$PDK" 2>/dev/null)"; then
    ENABLED="$(basename "$(dirname "$TARGET")")"
fi
if [ "$ENABLED" != "$PIN" ]; then
    if [ "${ENABLE_PDK:-0}" = 1 ]; then
        ciel enable --pdk-family "$PDK_FAMILY" "$PIN"
    else
        echo "PDK version mismatch."
        echo "  enabled: ${ENABLED:-<none>}"
        echo "  pinned:  $PIN  (librelane $("$VENV/bin/librelane" --version | head -1 | awk '{print $2}'))"
        echo "Fix with: ciel enable --pdk-family $PDK_FAMILY $PIN"
        echo "      or: ENABLE_PDK=1 $0"
        exit 1
    fi
fi

exec librelane --pdk "$PDK" --scl "$SCL" "$@" "$CONFIG"
