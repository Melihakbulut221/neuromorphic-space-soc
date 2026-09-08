# Licensing map and publication scope

This file is the map `docs/14-licensing-decision.md` section 6.4 calls
for, and the scope boundary its section 9 stage 1 calls for, in one
place. The memo is the decision and the argument; this is the answer
applied to paths.

Signed 2026-09-09. Rows 1 to 9 of `docs/14` section 11 accepted as
defaulted.

## 1. The three licences

| Class | Licence | Text |
|---|---|---|
| RTL, testbenches, constraints, formal jobs, flow configuration | `CERN-OHL-W-2.0` | `LICENSES/CERN-OHL-W-2.0.txt` |
| Generators, golden models, harnesses, flow drivers, analysis, CI | `Apache-2.0` | `LICENSES/Apache-2.0.txt` |
| Documents in `docs/` and measurement data | `CC-BY-4.0` | `LICENSES/CC-BY-4.0.txt` |

**Why the hardware is reciprocal and the software is not.** A weakly
reciprocal hardware licence asks that a modified version of *this
design* be published; it does not reach the chip a user puts it in.
That is the boundary `docs/14` section 6.1 wanted. The tooling is
permissive for a stated reason rather than a preference: `docs/13`
promises the redundancy-survival checker and the reproducible test cases
**upstream**, to yosys, LibreLane and IHP-Open-PDK, and none of those
projects takes reciprocal code (`docs/14` section 6.5). Anything written
to be merged into a named upstream project is `Apache-2.0` from the
moment it is written.

## 2. Every tracked path, in or out

471 tracked files. Nothing is unlisted.

| Path | Files | Licence | Published |
|---|---|---|---|
| `hw/rtl/` | 10 | CERN-OHL-W-2.0 | yes — the frozen pilot, `docs/34` |
| `hw/soc/` | 213 | CERN-OHL-W-2.0 for `.v .vh .sv .sdc .sby .tcl`, Apache-2.0 for the rest | yes, except the two ISC files below |
| `hw/tb/` | 26 | CERN-OHL-W-2.0 / Apache-2.0 by type | yes |
| `hw/openlane/` | 37 | CERN-OHL-W-2.0 | yes |
| `hw/fpga/` | 4 | CERN-OHL-W-2.0 / Apache-2.0 by type | yes |
| `formal/` | 24 | CERN-OHL-W-2.0 | yes |
| `tt/` | 29 | CERN-OHL-W-2.0, scaffolding Apache-2.0 as received | yes — this is the shuttle submission |
| `regmap/` | 4 | Apache-2.0 | yes |
| `sw/golden/`, `sw/tests/` | 27 | Apache-2.0 | yes |
| `scripts/` | 4 | Apache-2.0 | yes |
| `.github/` | 1 | Apache-2.0 | yes |
| `docs/` | 83 | CC-BY-4.0 | **all but four**, see 2.1 |
| root files | 7 | by type; `verification-log.tsv` is CC-BY-4.0 data | yes |

### 2.1 What is held back, and why

`docs/14` section 11 row 6, answer (b) as amended:

| Held | Reason |
|---|---|
| `docs/05` section 3 | market and product-line material. Not a licence question and not a research result |
| `docs/06` | funding and shuttle commercials |
| `docs/13` | the NLnet application text, until it is submitted |

`docs/14` itself was in that list and is **not** held any more: (b)'s
condition was that it be a decision rather than a draft, and it is now
signed. It publishes with the rest.

Nothing else is held. In particular the negative results, the withdrawn
claims and the documents that correct earlier documents are published,
because a record that only carries what worked is not the record this
project keeps.

### 2.2 Not this project's licence to choose

| File | Licence | Source |
|---|---|---|
| `hw/soc/rvformal/insns/insn_div.v`, `insn_rem.v` | ISC | corrected copies of `YosysHQ/riscv-formal` models, notice inline, `LICENSES/ISC.txt` |
| `tt/.github/`, `tt/.devcontainer/`, `tt/.vscode/`, `tt/src/config.json`, `tt/test/Makefile`, `tt/test/tb.v`, `tt/test/requirements.txt` | Apache-2.0 as received | `TinyTapeout/ttihp-verilog-template` at `6598bef4d315`; `--diff-template` proves the claim |

Everything else third-party is **fetched, not vendored**:
`hw/soc/tools.soc.mk` pulls six upstream trees and two toolchains into
gitignored directories, pinned by commit or sha256, and `soc-toolcheck`
refuses a dirty checkout. `git ls-files` returns nothing under
`hw/soc/ext/`, `hw/soc/tools/`, `hw/soc/gen/`, `hw/soc/genrvfi/` or
`tt/tt/`.

## 3. How the map is kept true

```bash
python3 scripts/spdx_check.py          # exit 1 on an untagged or mis-tagged source file
python3 scripts/spdx_check.py --list   # the classification of all 471 files
```

309 files carry an inline tag; 162 are covered by path in
`.reuse/dep5`, each with a stated reason for why it cannot carry one.
The check runs in CI. It is the same standard the flow guards apply to
themselves: the claim is made mechanically, not editorially.

Generated files carry their tag because **their generator emits it** --
`regmap/generate.py`, `regmap/generate_memmap.py` and
`scripts/gen_tt_submission.py`. If one of them fails the check, re-run
the generator; do not edit the output.
