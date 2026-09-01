#!/usr/bin/env bash
# Synthesise one named Ibex configuration onto ihp-sg13g2 with Yosys.
#
#   syn_ibex.sh <config> <clock_period_ns> [out_root]
#
# Configurations (see docs/38 for why each exists):
#
#   small          docs/03's stated baseline: RV32IMC, 2-stage, no PMP,
#                  no security features. Measured only so the number
#                  docs/03 estimated has a like-for-like comparison.
#   small-pmp      THE CANDIDATE. small + PMP, 4 regions. docs/09 part B
#                  track 3 option S2 makes PMP the isolation mechanism of
#                  the supervisor, so a no-PMP core does not implement
#                  the chosen software architecture.
#   small-pmp-sec  small-pmp + SecureIbex. In ibex_top.sv SecureIbex is
#                  the single switch behind Lockstep, RegFileLockstepECC,
#                  DummyInstructions, MemECC and ResetAll (localparams,
#                  lines 212-216). This is the configuration docs/03's
#                  fault-tolerance argument actually refers to.
#
# All three use RegFileFF, not the latch register file the upstream
# synthesis flow forces: every architectural state element has to be a
# nameable flop for the fault-injection flow.

set -euo pipefail

CFG=${1:?config name}
PERIOD_NS=${2:?clock period in ns}
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT_ROOT=${3:-$SOC_DIR/out}
OUT=$OUT_ROOT/$CFG

# THIS SCRIPT DEFAULTS TO `upstream` AND THE SOC FLOWS DEFAULT TO
# `secded`, and the difference is deliberate.
#
# The configuration names below -- small, small-pmp, small-pmp-sec --
# are docs/38's, and every area and timing number in that document is
# quoted against them. A tool that silently measured a register file
# this project substituted would make those names describe something
# they do not, and docs/38 section 8.4's 275,682.6198 um2 would stop
# reproducing without anything saying so.
#
# The hardened core is measured by asking for it:
#     IBEX_REGFILE=secded flow/syn_ibex.sh small-pmp 20 out/h43-secded
# which is what docs/43 section 7.1 runs, beside the upstream row, in
# the same session.
IBEX_REGFILE=${IBEX_REGFILE:-upstream}
export IBEX_REGFILE
# shellcheck source=hw/soc/flow/ibex_sources.sh
. "$SOC_DIR/flow/ibex_sources.sh"

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${YOSYS:?}" "${SG13G2_TYP:?}"

# Shared defaults, then per-configuration overrides.
P_BASEISA=0        # ibex_pkg::BaseIsaRV32I -- no CHERIoT
P_RV32E=0
P_RV32M=2          # ibex_pkg::RV32MFast
P_RV32B=0          # ibex_pkg::RV32BNone
P_RV32ZC=0         # ibex_pkg::RV32Zca -- plain "C", no Zcb/Zcmp
P_REGFILE=0        # ibex_pkg::RegFileFF
P_BTALU=0
P_WBSTAGE=0
P_ICACHE=0
P_ICACHEECC=0
P_ICACHESCR=0
P_BP=0
P_DBGTRIG=0
P_SECURE=0
P_PMPEN=0
P_PMPGRAN=0
P_PMPNUM=4
P_MHPMNUM=0
P_MHPMW=40

case "$CFG" in
  small)          ;;
  small-pmp)      P_PMPEN=1 ;;
  small-pmp-sec)  P_PMPEN=1; P_SECURE=1 ;;
  *) echo "unknown config: $CFG" >&2; exit 2 ;;
esac

rm -rf "$OUT"; mkdir -p "$OUT"

# ABC is given the same period the SDC will use. No uprate: upstream's
# flow subtracts a fudge from the period before handing it to ABC, which
# makes the reported frequency depend on a magic number. Here the number
# ABC optimises for and the number STA checks are the same number.
cat > "$OUT/abc.constr" <<EOF
set_driving_cell sg13g2_buf_4
set_load 0.005
EOF

IBEX_SRCS=$(ibex_sources "$SOC_DIR" | tr '\n' ' ')

sed -e "s|@IBEX_SRCS@|$IBEX_SRCS|g" \
    -e "s|@GEN@|$SOC_DIR/gen|g" \
    -e "s|@RTL@|$SOC_DIR/rtl|g" \
    -e "s|@LIB@|$SG13G2_TYP|g" \
    -e "s|@OUT@|$OUT|g" \
    -e "s|@CFG@|$CFG|g" \
    -e "s|@ABC_D@|$PERIOD_NS|g" \
    -e "s|@P_BASEISA@|$P_BASEISA|g" \
    -e "s|@P_RV32E@|$P_RV32E|g" \
    -e "s|@P_RV32M@|$P_RV32M|g" \
    -e "s|@P_RV32B@|$P_RV32B|g" \
    -e "s|@P_RV32ZC@|$P_RV32ZC|g" \
    -e "s|@P_REGFILE@|$P_REGFILE|g" \
    -e "s|@P_BTALU@|$P_BTALU|g" \
    -e "s|@P_WBSTAGE@|$P_WBSTAGE|g" \
    -e "s|@P_ICACHE@|$P_ICACHE|g" \
    -e "s|@P_ICACHEECC@|$P_ICACHEECC|g" \
    -e "s|@P_ICACHESCR@|$P_ICACHESCR|g" \
    -e "s|@P_BP@|$P_BP|g" \
    -e "s|@P_DBGTRIG@|$P_DBGTRIG|g" \
    -e "s|@P_SECURE@|$P_SECURE|g" \
    -e "s|@P_PMPEN@|$P_PMPEN|g" \
    -e "s|@P_PMPGRAN@|$P_PMPGRAN|g" \
    -e "s|@P_PMPNUM@|$P_PMPNUM|g" \
    -e "s|@P_MHPMNUM@|$P_MHPMNUM|g" \
    -e "s|@P_MHPMW@|$P_MHPMW|g" \
    "$SOC_DIR/syn/ibex_syn.ys.in" > "$OUT/ibex_syn.ys"

"$YOSYS" -l "$OUT/syn.log" -s "$OUT/ibex_syn.ys"
echo "== $CFG synthesised into $OUT"
