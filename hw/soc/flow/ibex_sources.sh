#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

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
#
# IBEX_FAULT_PORT selects, and it is a SECOND and larger cost:
#
#   1  hw/soc/genp/ibex_top.v, written by flow/ibex_fault_port.py from
#      the sv2v output, with one output port added and driven -- so a
#      corrected upset in the register file can be counted by
#      soc_busstat and read by software. hw/soc/gen/ibex_top.v is
#      EXCLUDED. This is what every flow that builds `soc_top` needs,
#      because soc_top.v connects the port unconditionally; an unpatched
#      `ibex_top` fails at elaboration with the port's name in the
#      message.
#   0  (default) hw/soc/gen/ibex_top.v, unmodified. This is the design
#      docs/38 and docs/43 measured, and it stays reachable so their
#      area and timing numbers reproduce.
#
# The two families of flow default differently here for the same reason
# they do for IBEX_REGFILE, and docs/43 section 3.1 gives that reason:
# the SoC flows build the design as it would ship, and the standalone
# measurement flows reproduce a published number unless asked not to.
# docs/44 section 4 states what the patch costs the pinning story.
#
# IBEX_GEN selects WHICH sv2v output tree the list is read from, and it
# is the third selector because docs/63 needs a core that carries the
# RVFI trace ports:
#
#   gen      (default) the tree hw/soc/flow/sv2v_ibex.sh writes with no
#            extra defines. This is what the SoC is built and measured
#            from and what every flow before docs/63 reads.
#   genrvfi  the same conversion of the same pinned commit with
#            `--define=RVFI`, adding the 45 trace ports of ibex_top.sv
#            line 138. It is a SEPARATE tree and not a replacement:
#            `gen` must go on reproducing byte-identically, because
#            docs/38 to docs/62's numbers were measured from it.
#
# IBEX_FAULT_PORT=1 is REFUSED with anything but the default tree.
# flow/ibex_fault_port.py rewrites a specific ibex_top.v and nothing has
# checked it against an RVFI one, so the combination is an error here
# rather than a wrong netlist somewhere downstream.

ibex_sources () {
  local soc_dir=$1
  local mode=${IBEX_REGFILE:-secded}
  local port=${IBEX_FAULT_PORT:-0}
  local gendir=${IBEX_GEN:-gen}
  local f

  case "$mode" in
    secded|upstream) ;;
    *) echo "IBEX_REGFILE must be 'secded' or 'upstream', got '$mode'" >&2
       return 2 ;;
  esac
  case "$port" in
    0|1) ;;
    *) echo "IBEX_FAULT_PORT must be 0 or 1, got '$port'" >&2
       return 2 ;;
  esac
  case "$gendir" in
    gen|genrvfi) ;;
    *) echo "IBEX_GEN must be 'gen' or 'genrvfi', got '$gendir'" >&2
       return 2 ;;
  esac
  if [ "$port" = 1 ] && [ "$gendir" != gen ]; then
    echo "IBEX_FAULT_PORT=1 is only defined for IBEX_GEN=gen" >&2
    return 2
  fi
  if [ ! -d "$soc_dir/$gendir" ]; then
    echo "$soc_dir/$gendir does not exist. Run flow/sv2v_ibex.sh." >&2
    return 2
  fi

  if [ "$port" = 1 ]; then
    python3 "$soc_dir/flow/ibex_fault_port.py" \
            "$soc_dir/gen" "$soc_dir/genp" "$mode" >&2 || return 2
  fi

  for f in "$soc_dir"/$gendir/*.v; do
    if [ "$mode" = "secded" ] && \
       [ "$(basename "$f")" = "ibex_register_file_ff.v" ]; then
      continue
    fi
    if [ "$port" = 1 ] && [ "$(basename "$f")" = "ibex_top.v" ]; then
      continue
    fi
    echo "$f"
  done

  if [ "$port" = 1 ]; then
    echo "$soc_dir/genp/ibex_top.v"
  fi

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
