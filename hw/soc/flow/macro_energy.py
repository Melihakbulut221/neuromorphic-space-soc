#!/usr/bin/env python3
"""SRAM macro energy from the Liberty tables and the measured access pattern.

    macro_energy.py act.json --window idle --corner typ_1p20V_25C

WHY THIS EXISTS BESIDE `report_power`.  OpenSTA responds to the macro
control-pin annotation -- the six macros move from 4.068 mW to 2.550 mW
at the typical corner between a busy window and an idle one -- but the
weighting it applies to a `when`-conditioned `internal_power` group is
not visible in any report it writes, and the arithmetic below does not
reproduce it.  So the macros are also priced directly, from the two
things that are not in doubt: the Liberty's own numbers, and the number
of clock edges the design spends in each of the macro's states.

The state is exhaustive because `soc_mem_sram.v` ties `A_REN` to
`!do_write`, so `A_WEN` and `A_REN` are complementary on every macro on
every cycle and only four of the eight `when` conditions can occur:

    A_MEN & !A_WEN &  A_REN   a read
    A_MEN &  A_WEN & !A_REN   a write
   !A_MEN & !A_WEN &  A_REN   deselected, while the SoC is not writing
   !A_MEN &  A_WEN & !A_REN   deselected, while the SoC writes elsewhere

The third of those is the one worth reading twice.  It is the state
every macro is in on every clock edge of an idle part, and the Liberty
charges **0.5559 pJ** for it on the 2048x64 and **0.3622 pJ** on the
1024x32, against **0** for the same macro with `A_REN` low.
"""

import argparse
import json
import re
import sys

PDK = ("/home/hasanmelih/.ciel/ciel/ihp-sg13g2/versions/"
       "c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c/ihp-sg13g2")

MACROS = {
    "RM_IHPSG13_1P_2048x64_c2_bm_bist": [
        ("u_ram.g_ram_2048x64.u_b0", "ram", 0),
        ("u_ram.g_ram_2048x64.u_b1", "ram", 1),
        ("u_ram.g_ram_2048x64.u_b2", "ram", 2),
        ("u_ram.g_ram_2048x64.u_b3", "ram", 3),
    ],
    "RM_IHPSG13_1P_1024x32_c2_bm_bist": [
        ("u_rom.g_rom_1024x32.u_b0", "rom", 0),
        ("u_rom.g_rom_1024x32.u_b1", "rom", 1),
    ],
}

# The corner names the SRAM Liberty uses. The fast one is characterised
# at -55 C where the standard cells are at -40 C, which is docs/47
# section 9's caveat and applies to power exactly as to timing.
SRAM_CORNER = {
    "nom_typ_1p20V_25C": "typ_1p20V_25C",
    "nom_slow_1p08V_125C": "slow_1p08V_125C",
    "nom_fast_1p32V_m40C": "fast_1p32V_m55C",
}


def read_lib(macro, corner):
    """Return (energies pJ per A_CLK rise by state, leakage in W)."""
    path = f"{PDK}/libs.ref/sg13g2_sram/lib/{macro}_{corner}.lib"
    txt = open(path).read()
    m = re.search(r"pin\(A_CLK\)(.*?)\n   \}\n", txt, re.S)
    if m is None:
        sys.exit(f"no A_CLK pin block in {path}")
    body = m.group(1)
    e = {}
    for cond, val in re.findall(
            r'when\s*:\s*"([^"]+)";\s*rise_power\("scalar"\)\{\s*'
            r'values \(([-0-9.eE]+)\)', body):
        e[re.sub(r"\s+", "", cond)] = float(val)
    leak = float(re.findall(r"cell_leakage_power\s*:\s*([0-9.eE+-]+)", txt)[-1])
    return e, leak * 1e-9, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--window", required=True)
    ap.add_argument("--corner", default="nom_typ_1p20V_25C")
    ap.add_argument("--period-ns", type=float, default=20.0)
    args = ap.parse_args()

    data = json.load(open(args.json))
    w = data["windows"][args.window]
    cycles = w["cycles"]
    d = w["derived"]
    sc = SRAM_CORNER[args.corner]

    total = 0.0
    total_leak = 0.0
    print(f"# window {args.window}, {cycles} cycles, corner {args.corner}, "
          f"period {args.period_ns} ns")
    print(f"{'macro':<28}{'reads':>10}{'writes':>10}{'desel-R':>12}"
          f"{'desel-W':>10}{'energy pJ':>14}{'power mW':>11}")
    for macro, insts in MACROS.items():
        e, leak, path = read_lib(macro, sc)
        E_rd = e["A_MEN&!A_WEN&A_REN"]
        E_wr = e["A_MEN&A_WEN&!A_REN"]
        E_dr = e["!A_MEN&!A_WEN&A_REN"]
        E_dw = e["!A_MEN&A_WEN&!A_REN"]
        for inst, pfx, k in insts:
            rd = d[f"{pfx}_rd{k}"]["high_cycles"]
            wr = d[f"{pfx}_wr{k}"]["high_cycles"]
            dr = d[f"{pfx}_dr{k}"]["high_cycles"]
            dw = d[f"{pfx}_dw{k}"]["high_cycles"]
            ej = (rd * E_rd + wr * E_wr + dr * E_dr + dw * E_dw) * 1e-12
            p = ej / (cycles * args.period_ns * 1e-9) if cycles else 0.0
            total += ej
            total_leak += leak
            print(f"{inst:<28}{rd:>10}{wr:>10}{dr:>12}{dw:>10}"
                  f"{ej * 1e12:>14.1f}{(p + leak) * 1e3:>11.6f}")
    dyn = total / (cycles * args.period_ns * 1e-9) if cycles else 0.0
    print(f"{'TOTAL dynamic':<28}{'':>42}{total * 1e12:>14.1f}"
          f"{dyn * 1e3:>11.6f}")
    print(f"{'TOTAL leakage':<28}{'':>56}{total_leak * 1e3:>11.6f}")
    print(f"{'TOTAL':<28}{'':>56}{(dyn + total_leak) * 1e3:>11.6f}")
    print(f"# energy per window: {total * 1e9:.4f} nJ dynamic + "
          f"{total_leak * cycles * args.period_ns * 1e-9 * 1e9:.4f} nJ leakage")


if __name__ == "__main__":
    main()
