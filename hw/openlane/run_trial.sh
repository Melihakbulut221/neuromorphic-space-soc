#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

#
# IHP SG13G2 hardening through LibreLane, rootless.
#
# Two designs live under hw/openlane/:
#   aer_fifo    -- the G0 trial harden (docs/12 section 4)
#   sram_pilot  -- the RM_IHPSG13 macro decision run (docs/12 section 7)
#
# Rootless by construction: no docker, no root, no system package installs.
# The toolchain is the one proven on SKY130 by the sibling projects --
# shim wrappers in ~/.local/opt/llbin that pin LD_LIBRARY_PATH per tool
# (the OpenROAD build ships a newer glibc that segfaults host binaries if
# it leaks into the ambient environment), plus a LibreLane virtualenv and
# an oss-cad-suite checkout for Yosys/Icarus. Nothing here is installed
# into the repository; see docs/12-sg13g2-flow-bringup.md for how each
# path was produced.
#
# Usage:
#   hw/openlane/run_trial.sh [librelane args]           # aer_fifo, full flow
#   hw/openlane/run_trial.sh -T OpenROAD.STAPrePNR      # synthesis + STA only
#   hw/openlane/run_trial.sh --design sram_pilot        # the macro run
#   ENABLE_PDK=1 hw/openlane/run_trial.sh               # switch ciel to the pin
#
# Environment overrides: SHIMS, VENV, OSS_CAD, PDK_ROOT.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# --design <name> selects hw/openlane/<name>/config.json; everything else
# is passed through to librelane untouched.
DESIGN=aer_fifo
ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --design) [ $# -ge 2 ] || { echo "--design needs a value"; exit 1; }
                  DESIGN="$2"; shift 2 ;;
        --design=*) DESIGN="${1#--design=}"; shift ;;
        *)        ARGS+=("$1"); shift ;;
    esac
done
CONFIG="$HERE/$DESIGN/config.json"
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

# The PDK version is pinned by LibreLane, not by us: each LibreLane
# release ships pdk_hashes.yaml naming the IHP-Open-PDK commit it was
# tested against. Reading the pin out of the installed wheel keeps this
# script correct across LibreLane upgrades instead of hard-coding a hash
# that silently goes stale.
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

# ciel keeps every downloaded version under $PDK_ROOT/ciel/<family>/versions
# and exposes exactly one through the $PDK_ROOT/<pdk> symlink. Both the
# LibreLane ciel wrapper and the config.tcl files resolve through that
# symlink, so an unnoticed mismatch means hardening against a PDK the tool
# was never tested on. Assert it.
LINK="$PDK_ROOT/$PDK"
# $PDK_ROOT/<pdk> -> ciel/<family>/versions/<hash>/<pdk>, so the version is
# the parent directory of the resolved link target. readlink -e (not -f)
# on purpose: -f canonicalises a path whose last component does not exist,
# so with no PDK enabled at all it would happily report basename(PDK_ROOT)
# as the enabled version and the <none> branch below could never be taken.
ENABLED=""
if TARGET="$(readlink -e "$LINK" 2>/dev/null)"; then
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

# --pdk must be given on the CLI, not only in config.json: LibreLane's ciel
# wrapper resolves and installs the PDK from the CLI option (default
# sky130A) BEFORE the config file is read, then points PDK_ROOT at that
# version's directory. With the default, config.json's "PDK": "ihp-sg13g2"
# is then looked up inside the sky130 tree and the run dies with
# "PDK not found".
exec librelane --pdk "$PDK" --scl "$SCL" ${ARGS[@]+"${ARGS[@]}"} "$CONFIG"
