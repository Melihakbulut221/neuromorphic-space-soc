#!/usr/bin/env bash
# The Ibex source list, in one place, with the register file selected.
#
# SOURCE THIS, do not run it:
#
#   . "$SOC_DIR/flow/ibex_sources.sh"
#   ibex_sources "$SOC_DIR"          # prints one path per line
#
# WHY THIS FILE EXISTS
#
# `docs/43-core-hardening.md` protects the architectural register file,
# which `docs/42` section 6.3 measured as 45 % of the core's flip-flops
# and 3.2 of its 4.9 design-weighted percentage points of wrong-or-dead
# outcome. `ibex_top` chooses among `ibex_register_file_ff`, `_fpga` and
# `_latch` by parameter, so a hardened implementation with the same
# module name and the same port list drops in -- and the drop-in is done
# HERE, in a file list, rather than by editing anything.
#
#   hw/soc/ext/ibex   pristine checkout at the pinned commit, untouched
#   hw/soc/gen        sv2v output, generated from it, untouched
#   soc_top.v         instantiates ibex_top, untouched
#
# The only thing that changes is which file supplies the module. That is
# the least invasive way to do this and it is still not nothing, and
# docs/43 section 3 prices it: an interface that moves upstream, a
# tracked file outside the pinned set, and a build whose Ibex is no
# longer bit-for-bit the one the commit names.
#
# IBEX_REGFILE selects:
#
#   secded    (default)  hw/soc/rtl/ibex_regfile_secded.v, and
#                        hw/soc/gen/ibex_register_file_ff.v is EXCLUDED.
#   upstream             hw/soc/gen/ibex_register_file_ff.v, and this
#                        project's file is excluded. This is the design
#                        docs/38, docs/39, docs/40 and docs/42 measured
#                        and it stays reachable so every one of those
#                        numbers can be reproduced.
#
# Exactly one of the two is ever in the list. Two files declaring
# `ibex_register_file_ff` would be a redeclaration error in Icarus and a
# silent first-wins in some other front ends, so the exclusion is done
# by construction rather than relied on.

ibex_sources () {
  local soc_dir=$1
  local mode=${IBEX_REGFILE:-secded}
  local f

  case "$mode" in
    secded|upstream) ;;
    *) echo "IBEX_REGFILE must be 'secded' or 'upstream', got '$mode'" >&2
       return 2 ;;
  esac

  for f in "$soc_dir"/gen/*.v; do
    if [ "$mode" = "secded" ] && \
       [ "$(basename "$f")" = "ibex_register_file_ff.v" ]; then
      continue
    fi
    echo "$f"
  done

  if [ "$mode" = "secded" ]; then
    echo "$soc_dir/rtl/ibex_regfile_secded.v"
    # hw/rtl/secded_enc.v and hw/rtl/secded_dec.v are READ from the
    # pilot's directory and never modified, exactly as hw/rtl/tmr_voter.v
    # already is. They are the codec docs/29 and docs/35 proved and
    # hw/tb/test_secded.py cross-checks against sw/golden/secded.py; a
    # copy under hw/soc/ would be a second implementation of the one
    # thing docs/38 section 8.5 objected to having two of.
    echo "$soc_dir/../rtl/secded_enc.v"
    echo "$soc_dir/../rtl/secded_dec.v"
  fi
}
