# 22 — Re-harden after the wave-5 pointer TMR, and the tile budget it breaks

Status: complete for IHP; the sky130 companion run did not converge in
detailed routing and section 5 reports it as what it is. Supersedes
specific figures in `docs/15`, `docs/18`, `docs/20` and `docs/21` — the
exact list, with replacement numbers, is section 6. **None of those
documents is edited here.**

Three jobs, all consequences of commit `c5a5a6e`:

1. **Close the last open wave-5 item.** `sw/tests/test_synthesis_guards.py`
   carries `test_pointer_tmr_survives_the_real_hardening_flow`, which
   counts the twelve AER pointer replica banks in the netlist LibreLane
   actually produced. It was skipping, because every run on disk
   predated `hw/rtl/aer_fifo.v`. Section 3 closes it.
2. **Re-derive the tile budget.** Every area and utilization figure on
   record predates two rounds of hardening — the `lif_core` memory ECC
   and now the pointer TMR. Section 2 is the new sign-off and section 4
   is the verdict.
3. **Refresh the cross-PDK run**, so `docs/18` is not left quoting a
   sky130 netlist three RTL revisions old. Section 5.

### Headline

- **The guard passes.** `test_pointer_tmr_survives_the_real_hardening_flow`
  now **PASSED**, not skipped. It counted **3 flip-flops under each of
  the twelve pointer replica banks** — 36 in total — in
  `tt/runs/wave5-ihp/final/nl/tt_um_melihakbulut_nssoc.nl.v`, out of
  **1,268** mapped flip-flops. The whole file is 17 passed, 0 skipped,
  0 failed. The configuration TMR is still 55 in each of three banks.
- **The IHP sign-off is clean on every deck.** 1,268 flip-flops,
  184,969 um2 of placed cells, 0 route DRC, 0 Magic DRC, **0 KLayout
  DRC**, 0 Netgen LVS on all seven counters, 0 antenna nets, and all
  three PVT corners closed at 20 ns with every violation counter at
  zero. Slow corner **+1.1554 ns**, which is **0.524 ns better** than
  `ihp-mix` despite a larger netlist — the third time in this project
  that a bigger hardened netlist has closed better.
- **The design no longer fits the 70 % planning criterion, and this is
  the finding that matters.** Utilization is **71.19 %**. At the
  criterion the design needs **264,241 um2** of placement rows against
  the **259,837 um2** the 4x2 core provides: a **shortfall of 4,404 um2,
  1.70 % of the core**. Where `docs/20` recorded 60.91 % and 13.0 %
  spare, and `docs/15` recorded 69.68 % and 0.46 % spare, this run
  records **71.19 % and minus 1.70 %**. The remaining headroom is gone
  and the design is over budget. Section 4.
- **The tile still closed physically.** 4x2 routed DRC-clean at 71.19 %.
  What has failed is the planning criterion, not the run. Those are
  different statements and section 4.2 keeps them apart, because the
  decision they support is different.
- **sky130 4x2 no longer routes.** Placement utilization went from
  66.98 % (`sky-04-tmr`) to **82.96 %**, and TritonRoute diverged —
  218,483 violations after the 0th optimization iteration, 348,149 after
  the 1st, still rising. The `docs/18` slow-corner miss could not be
  re-measured because there is no routed netlist to measure it on.
  Section 5.
- **Total power is measured again**: **5.119 mW** at 50 MHz on the
  typical corner, against the 4.36 mW `docs/21` carries from the pre-fix
  design and marks "not yet re-measured".

---

## 1. What was run, and against which sources

### 1.1 Toolchain

```
$ make -f tools.mk toolcheck
OSS_CAD_SUITE = /home/hasanmelih/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite
sby       = .../bin/sby
yosys     = .../bin/yosys
iverilog  = .../bin/iverilog
yosys version = 0.67+146 (pinned 0.67+146)
```

No mismatch warning. The hardening flow is the rootless LibreLane of
`docs/12` section 2.1, unchanged from `docs/20` section 1.1:

| Component | Version | Where it is pinned |
|---|---|---|
| LibreLane | 3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow` |
| Yosys (in-flow) | 0.67 | LibreLane wheel |
| Yosys (guards, `tools.mk`) | 0.67+146 | `OSS_CAD_SUITE` pin |
| ihp-sg13g2 PDK | `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` | LibreLane `pdk_hashes.yaml`, asserted by `run_ihp.sh` |
| sky130A PDK | `8afc8346a57fe1ab7934ba5a6056ea8b43078e71` | same, asserted by `run_sky130.sh` |
| Magic | 8.3.678 | `~/.local/opt/magic-8.3.678` |

**[fact]** for every row. Both run scripts read the PDK hash out of the
installed wheel and refuse to start on a mismatch, so neither run could
have hardened against an untested PDK.

### 1.2 Sources: the blob list, pinned

`docs/18` set the precedent that a run must name the source it consumed
and `docs/20` section 1.2 records why — a concurrent session rewrote
`hw/rtl/lif_core.v` between a run's lint step and its synthesis step and
the run directory held no evidence of which version it read. Every run
reported here is pinned with `hw/openlane/pin_rtl.py` against commit
**`c5a5a6e`** and reads a disposable snapshot by absolute path, not
`hw/rtl`:

```
c6f26c165faa81c97a27bce6644bc670f3b36542  hw/rtl/aer_fifo.v
b196828f65c271d849cad0ad21536c561d2079af  hw/rtl/lif_core.v
e6c1e646643840e2a553924b56dfab64022e5c39  hw/rtl/npu_regbank.v
9aaaa394e7a6ef855f5584fb85d53e688ac3e0b5  hw/rtl/npu_regs.vh
b5863d447f2ee1f1242993dab103fad4661bcf16  hw/rtl/pilot_top.v
89e62789ad016c7cb51ad69247f6066335074f8c  hw/rtl/scrub.v
f7c7ec187a0df4eb09a8405dcda285de0fc2e44e  hw/rtl/secded_dec.v
b5710b8a679c3e378e74953b621b99f0d8dc3014  hw/rtl/secded_enc.v
62b5f4d2a1eae095d9d4a8634ede55237e2c924d  hw/rtl/tmr_voter.v
e294afcf03e1947906086beeba2fd0c40b29441d  hw/rtl/tt_um_melihakbulut_nssoc.v
```

**[fact, `hw/openlane/pin_rtl.py c5a5a6e`, which prints the blob of every
file it writes]**. The working tree was clean at `c5a5a6e` and
`git ls-tree HEAD hw/rtl` matches this list blob for blob, so the
snapshot is the committed tree and not a dirty variant of it **[fact]**.

`tt/src/*.v` carried the same eight blobs at the time of the run, so the
submission copies and `hw/rtl` were identical, not merely equivalent
**[fact, `git hash-object` on both trees]**. The two files that carry
the substance of this wave: **`aer_fifo.v` at `c6f26c16`** is the
revision that puts three `aer_ptr_bank` instances behind a voter on each
of the four queue pointers, and **`pilot_top.v` at `b5863d44`** is the
revision that connects the `lif_core` ECC status ports.

The blob list is the record; the snapshot directory is disposable and
regenerable from `c5a5a6e`.

### 1.3 The runs

| Tag | Path | PDK | Config | Purpose |
|---|---|---|---|---|
| `wave5-ihp` | `tt/runs/wave5-ihp` | ihp-sg13g2 | `tt/src/config_merged.json`, pinned | the sign-off; section 2 |
| `ihp-klayoutdrc-w5` | `hw/openlane/pilot_ihp/runs/ihp-klayoutdrc-w5` | ihp-sg13g2 | `+ RUN_KLAYOUT_DRC: 1` | the KLayout deck; section 2.3 |
| `sky-08-ptrtmr` | `hw/openlane/pilot_sky130/runs/sky-08-ptrtmr` | sky130A | `pilot_sky130/config.json`, pinned | cross-PDK; section 5 |

`wave5-ihp` runs the submission's own `config_merged.json` — the
configuration the Tiny Tapeout GDS action would use — at the 4x2 tile
(854.40 x 313.74 um), `CLOCK_PERIOD: 20`,
`SYNTH_HIERARCHY_MODE: deferred_flatten`. It is written into `tt/runs/`
rather than `hw/openlane/pilot_ihp/runs/` on purpose, following the
`tmr-reharden` precedent of `docs/20` section 2: `tt/runs/` is one of the
two trees `sw/tests/test_synthesis_guards.py` scans for a real hardening
netlist, and `hw/openlane/pilot_ihp/runs/` is not. A re-harden that
landed only in the `pilot_ihp` tree would have produced every number in
section 2 and still left the guard skipping.

`SYNTH_HIERARCHY_MODE: deferred_flatten` is required, not cosmetic. The
`keep_hierarchy` banks otherwise leave `$paramod` module types in the
mapped netlist that `Checker.YosysUnmappedCells` counts as unmapped
instances and aborts on. `docs/20` section 3.3 measures what it buys and
what it costs; nothing here revisits that. This run reports
`design__instance_unmapped__count: 0` **[fact,
`tt/runs/wave5-ihp/final/metrics.json`]**.

Every number below is extracted with `hw/openlane/signoff_report.py`
rather than by hand-grep, so runs being compared are read the same way.

---

## 2. The re-hardened IHP sign-off

`tt/runs/wave5-ihp`, ihp-sg13g2, 4x2 tile, completed with
`flow__errors__count: 0` and `design__violations: 0` **[fact,
`tt/runs/wave5-ihp/final/metrics.json`]**.

### 2.1 Sign-off table, beside the two it supersedes

`ihp-mix` is the run `docs/15` section 4.1 currently reports and is the
correct predecessor: it is the last run on the same flow and the same
submission config, and it carries the memory ECC and `MIX` but not the
pointer TMR. `tmr-reharden` is included because `docs/20` section 2.1 is
still the document a reader is most likely to reach for.

| Quantity | `tmr-reharden` (`docs/20` §2.1) — **superseded** | `ihp-mix` (`docs/15` §4.1) — **superseded** | **`wave5-ihp`** | Move, mix → wave5 |
|---|---|---|---|---|
| Mapped flip-flops | 1,155 | 1,235 | **1,268** | **+33** |
| Flip-flop cell type | all `sg13g2_dfrbpq_1` | all `sg13g2_dfrbpq_1` | **all `sg13g2_dfrbpq_1`** | — |
| Synthesis cells | 7,791 | 9,487 | **9,754** | +2.81 % |
| Synthesis cell area | 126,647 um2 | 147,649 um2 | **151,556.53 um2** | +2.65 % |
| Placed cells, excl. fill | 10,164 | 12,048 | **12,322** | +2.27 % |
| Instances incl. fill | 22,940 | 23,763 | **23,584** | -0.75 % |
| **Placed cell area** | 158,268 um2 | 181,043 um2 | **184,969 um2** | **+2.17 %** |
| of which sequential | 56,582 um2 | 60,501 um2 | **62,117.8 um2** | +2.67 % |
| of which timing-repair buffers | 28,181 um2 (2,213) | 29,885 um2 (2,394) | **29,721.7 um2 (2,389)** | -0.55 % |
| of which clock buffers | 3,422 um2 | 3,153 um2 | **3,224.19 um2** | +2.24 % |
| Die area | 268,059 um2 | 268,059 um2 | **268,059 um2** | fixed by the tile |
| Core area | 259,837 um2 | 259,837 um2 | **259,837 um2** | fixed by the tile |
| **Utilization** | 60.91 % | 69.6756 % | **71.1867 %** | **+1.511 pts** |
| Routed wirelength | 386,429 um | 459,379 um | **469,324 um** | +2.16 % |
| Route (TritonRoute) DRC | 0 | 0 | **0** | — |
| **Magic DRC** | 0 | 0 | **0** | — |
| **KLayout DRC** | not run | not run | **0** (§2.3) | closed |
| **Netgen LVS** | 0 | 0 | **0** | — |
| LVS unmatched nets / devices / pins / properties | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | **0 / 0 / 0 / 0** | — |
| **Antenna-violating nets** | 0 | 0 | **0** | — |
| Antenna-violating pins | 0 | 0 | **0** | — |
| Antenna diodes inserted | 0 | 0 | **4** | +4 |
| Unmapped instances | 0 | 0 | **0** | — |
| Power-grid violations | 0 | 0 | **0** | — |
| Disconnected pins | 6 | 6 | **6** | the 6 unused TT wrapper inputs |
| Max-fanout counter | 77 | 82 | **85** | not gated; see `docs/15` §5.3 |
| `design__violations` | 0 | 0 | **0** | — |
| `flow__errors__count` | 0 | 0 | **0** | — |
| Worst IR drop, VPWR | 0.489 mV | — | **0.738 mV (0.06 %)** | indicative; no `VSRC_LOC_FILES` |
| **Total power, 50 MHz typical** | — | — | **5.119 mW** | see below |
| Summed step runtime | 36.3 min | 64.8 min | **55.1 min** | not comparable |

**[fact for every `wave5-ihp` entry; the Move column is arithmetic on two
measured numbers and is therefore an estimate.]** Areas and counts from
`final/metrics.json` (`design__instance__area__stdcell`,
`design__instance__utilization`, `design__instance__count`); flip-flop
and synthesis figures from `06-yosys-synthesis/reports/stat.json`.

Runtime carries no delta. Three LibreLane runs executed concurrently on
this machine, so wall-clock and summed step runtime here measure
scheduling, not work — the same caution `docs/20` section 5.4 records.

Manufacturability report: **Antenna Passed, LVS Passed, DRC Passed** —
three `Passed` lines, the `docs/12` section 4.1 bar **[fact,
`72-misc-reportmanufacturability/manufacturability.rpt`]**.

**Total power.** `power__total` is **5.1187 mW** at the typical corner —
4.214 mW internal, 0.898 mW switching, 6.03 uW leakage **[fact,
`final/metrics.json`]**. `docs/21` section 7.2 carries 4.36 mW from the
pre-fix design and marks it "not yet re-measured"; this is the
measurement, and it is +17.4 % on a design that has grown 35.9 % in
placed area since that figure was taken **[estimate, arithmetic on two
measured numbers]**.

### 2.2 Where the +33 flip-flops went

Counted by instance path in the two final netlists rather than inferred:

| Scope | `ihp-mix` | **`wave5-ihp`** | Delta |
|---|---|---|---|
| `u_pilot.u_evq_in` | 95 | **107** | **+12** |
| `u_pilot.u_evq_out` | 87 | **99** | **+12** |
| `u_pilot.u_cfg_{a,b,c}` | 165 | **165** | 0 |
| `u_pilot`, other | 886 | **895** | +9 |
| wrapper | 2 | **2** | 0 |
| **Total** | **1,235** | **1,268** | **+33** |

**[fact, `hw/openlane/pilot_ihp/runs/ihp-mix/final/nl/` and
`tt/runs/wave5-ihp/final/nl/`, counted by instance prefix over cells
matching `sg13g2_s?df`.]**

The +24 across the two queues is exactly the pointer TMR and the
arithmetic is closed, not approximate. Each queue held 2 pointers x 3
bits = 6 pointer flip-flops; it now holds 6 banks x 3 bits = 18. That is
+12 per queue, +24 over both, and the section 3 census confirms the
destination bank by bank.

The remaining **+9** is in `pilot_top`'s own scope and belongs to the
`13c52351` → `b5863d44` revision, which connects the `lif_core` ECC
status ports — items 8 and 9 of the `docs/15` section 8.5 developer
list. It is **not** pointer TMR and should not be attributed to it
**[estimate on the attribution; the +9 and its scope are fact]**. The
configuration TMR is untouched at 3 x 55, as it must be.

### 2.3 Timing, three corners, post-route with OpenRCX parasitics

| Corner | `tmr-reharden` — **superseded** | `ihp-mix` — **superseded** | **`wave5-ihp`** | Move, mix → wave5 |
|---|---|---|---|---|
| `nom_slow_1p08V_125C` | +6.4359 ns | +0.6315 ns | **+1.1554 ns** | **+0.524 ns** |
| `nom_typ_1p20V_25C` | +11.4227 ns | +7.7094 ns | **+8.0521 ns** | +0.343 ns |
| `nom_fast_1p32V_m40C` | +14.1670 ns | +11.9259 ns | **+12.1355 ns** | +0.210 ns |

Setup violations 0, hold violations 0, max-cap violations 0, max-slew
violations 0, on all three corners. Worst hold slack **+0.6204 ns** on
the slow corner and **+0.1093 ns** on the fast corner. **[fact,
`55-openroad-stapostpnr/summary.rpt` and `final/metrics.json`.]**

**The design is 0.524 ns faster on the slow corner than the run it
replaces, while carrying 33 more flip-flops and 2.17 % more placed
area.** That is the third time this has happened on this design —
`docs/20` section 2.2 saw +1.122 ns from the TMR fix, `docs/15` section
4.6 saw +0.228 ns from `MIX` — and the pattern is now consistent enough
to be worth stating as a caution rather than a surprise: **on this design
netlist size does not predict slack, in either direction.** Anyone
sizing a future increment from an area delta should not also assume it
buys or costs timing.

Read as frequency: +1.1554 ns at a 20 ns period is an 18.845 ns critical
path and a post-route slow-corner Fmax of about **53.1 MHz**, against
the 50 MHz `tt/info.yaml` declares — up from `ihp-mix`'s 51.6 MHz
**[estimate, arithmetic on a measured slack]**.

### 2.4 The KLayout deck, now closed on IHP

`docs/20` section 2.3 records that KLayout DRC did not run on the IHP
re-harden, because the Tiny Tapeout config sets `RUN_KLAYOUT_DRC: 0` and
`RUN_KLAYOUT_XOR: 0` under the comment "Save some time", and `docs/20`
section 9 named closing it as a follow-up. It is closed here, and it is
closed the same way `docs/20` section 11 closed it for the previous
netlist: a variant config that differs from the submission config in
that one key.

`hw/openlane/pilot_ihp/runs/ihp-klayoutdrc-w5` reports **KLayout DRC =
0** **[fact, `klayout__drc_error__count`, `final/metrics.json`]**.

The variant is worth more than its own result, because it is also a
reproducibility control. Every other number in it is **identical** to
`wave5-ihp` — 1,268 flip-flops, 9,754 synthesis cells, 151,556.5296 um2
of synthesis area, 12,322 placed cells, 184,969 um2 placed, 0.711867
utilization, 469,324 um of routed wirelength, 4 antenna diodes, +1.1554
/ +8.0521 / +12.1355 ns on the three corners **[fact, both
`final/metrics.json`]**. Two runs from two different config files, one
reading `tt/src`-derived paths and one reading `hw/rtl`-derived paths,
produced the same layout to the last digit. The flow is deterministic on
this design and the 71.19 % of section 4 is not a scheduling artefact of
the concurrent execution.

`RUN_KLAYOUT_XOR` remains 0 on IHP. It was not run and is not claimed.

### 2.5 What is not in this sign-off

Unchanged from `docs/20` section 2.3 and `docs/18` section 7: no
signal-integrity analysis; no `VSRC_LOC_FILES`, so the IR figures are
indicative rather than sign-off; `Yosys.EQY` gated off, so there is no
formal equivalence check between RTL and final netlist; and the
Magic/KLayout XOR is not run on IHP. The power figure in 2.1 is a flow
estimate from switching activity defaults, not a measured or annotated
power analysis.

---

## 3. The guard: it passes, and what it counted

This is the item wave 5 left open, and it is not a routine regression.
The project has already shipped a TMR that synthesis silently merged
away — `docs/21` section 6.3 and the header of
`sw/tests/test_synthesis_guards.py` record it — and RTL simulation is
structurally incapable of seeing a structure the mapper deletes. Only a
cell count in the real netlist catches it.

Before this work:

```
SKIPPED test_pointer_tmr_survives_the_real_hardening_flow
  every LibreLane run on disk predates aer_fifo.v, which is where the
  pointer banks are declared; re-harden to close this check
```

That skip was correct behaviour and worth preserving as such: the test
declines to assert a property it cannot observe, and its skip condition
is deliberately about **provenance** (does a run postdate the RTL that
declares the banks?) rather than about the netlist, because a
netlist-shaped skip would skip on exactly the symptom the file exists to
catch. `tt/runs/wave5-ihp` is the run that satisfies it.

After:

```
$ .venv/bin/python -m pytest sw/tests/test_synthesis_guards.py -v
...
sw/tests/test_synthesis_guards.py::test_config_tmr_survives_the_real_hardening_flow PASSED
sw/tests/test_synthesis_guards.py::test_pointer_tmr_survives_the_real_hardening_flow PASSED
======================== 17 passed in 184.09s (0:03:04) ========================
```

**17 passed, 0 skipped, 0 failed [fact].**

What it counted, in
`tt/runs/wave5-ihp/final/nl/tt_um_melihakbulut_nssoc.nl.v` — the shipped
netlist, after placement, CTS and routing have all had a chance to touch
it, not a model of synthesis:

| Bank | Flip-flops | | Bank | Flip-flops |
|---|---|---|---|---|
| `u_evq_in.u_wptr_a` | **3** | | `u_evq_out.u_wptr_a` | **3** |
| `u_evq_in.u_wptr_b` | **3** | | `u_evq_out.u_wptr_b` | **3** |
| `u_evq_in.u_wptr_c` | **3** | | `u_evq_out.u_wptr_c` | **3** |
| `u_evq_in.u_rptr_a` | **3** | | `u_evq_out.u_rptr_a` | **3** |
| `u_evq_in.u_rptr_b` | **3** | | `u_evq_out.u_rptr_b` | **3** |
| `u_evq_in.u_rptr_c` | **3** | | `u_evq_out.u_rptr_c` | **3** |

Twelve banks, `PTR_W = 3` in every one, **36 pointer flip-flops** out of
**1,268** in the netlist. The configuration domain alongside it reads
**55 under each of `u_cfg_a`, `u_cfg_b`, `u_cfg_c`** **[fact, counted
with the test's own `_is_flop` predicate over the same file]**.

Three things about this result are worth keeping.

- **It counts cells, not names.** `docs/20` section 3.3 measured that
  marking replicas `(* keep *)` leaves the wire names in the netlist
  while the storage disappears. Every number above is an instantiated
  `sg13g2_*` flip-flop with an instance path, which is the thing that
  becomes silicon.
- **The hazard here was sharper than in the configuration domain, and it
  did not fire.** All three replicas of a pointer are loaded from one
  net — the voted next pointer — which is precisely the signature
  `opt_merge` hashes on. Without the per-replica storage transform the
  collapse would have been the expected outcome, not a risk. The
  transform held.
- **The synthesis netlist agrees with the final netlist.** The same
  census over `06-yosys-synthesis/tt_um_melihakbulut_nssoc.nl.v` gives
  the same twelve threes on both PDKs **[fact]**, so nothing downstream
  of mapping ate a bank either.

`test_config_tmr_survives_the_real_hardening_flow` also passes against
this run, so both replicated domains are now witnessed in the same
shipped artefact.

---

## 4. Does it still fit 4x2, and with how much margin

### 4.1 The numbers

| Quantity | Value |
|---|---|
| 4x2 die | 854.40 x 313.74 um = 268,059 um2 |
| 4x2 core (placement rows inside the tile margins) | 259,837 um2 |
| Placed cell area | **184,969 um2** |
| **Achieved utilization** | **71.1867 %** |
| Free core area | 74,868 um2 (28.81 %) |
| Core needed at the 70 % criterion | **264,241 um2** |
| **Core shortfall against the criterion** | **-4,404 um2, or -1.70 % of the core** |
| Budget consumed | **101.70 %** |

**[fact for die, core, placed area and utilization,
`tt/runs/wave5-ihp/final/metrics.json`; the criterion arithmetic is an
estimate on measured areas.]** The die and core have not moved at any
step since `tt-harden`: 268,059 um2 and 259,837 um2 throughout, so the
entire utilization history is the design growing inside a fixed tile.

The history, on one criterion, from one script:

| Run | Placed cells | Utilization | Core needed at 70 % | Spare against the criterion |
|---|---|---|---|---|
| `tt-harden` (pre-fix) | 136,107 um2 | 52.38 % | 194,439 um2 | +65,398 um2 (**+25.17 %**) |
| `tmr-reharden` (`docs/20` §2.4) | 158,268 um2 | 60.91 % | 226,097 um2 | +33,740 um2 (**+12.99 %**) |
| `ihp-memecc` | 180,651 um2 | 69.52 % | 258,073 um2 | +1,764 um2 (**+0.68 %**) |
| `ihp-mix` (`docs/15` §4.1) | 181,043 um2 | 69.68 % | 258,633 um2 | +1,204 um2 (**+0.46 %**) |
| **`wave5-ihp`** | **184,969 um2** | **71.19 %** | **264,241 um2** | **-4,404 um2 (-1.70 %)** |

**[fact for the placed-area and utilization columns; the last two columns
are arithmetic on them.]**

### 4.2 The verdict, stated plainly

**The design no longer fits 4x2 at the 70 % planning criterion. It is
over budget by 4,404 um2, which is 1.70 % of the core.** `docs/20`
recorded 60.91 % utilization and 13.0 % spare; `docs/15` had already
superseded that with 69.68 % and 0.46 % spare; this run lands at
**71.19 % and minus 1.70 %**. The margin is not thin, it is negative.
`docs/15` section 4.1's sentence "The pilot fits 4x2 and no further run
is needed to say so" was true of `ihp-mix` and is **not true of
`c5a5a6e`**.

Two separate statements have to be kept apart here, because conflating
them is how a shuttle submission goes wrong in either direction.

- **The flow closed the tile.** `wave5-ihp` placed, routed and signed
  off at 71.19 % with 0 route DRC, 0 Magic DRC, 0 KLayout DRC, 0 LVS, 0
  antenna violations and 1.16 ns of slow-corner setup slack. If the only
  question were "does a GDS exist that passes the decks at 4x2", the
  answer from this run is yes.
- **The planning criterion is breached.** The 70 % figure is not a tool
  limit; it is the margin `docs/15` section 4.5 reserves for the things
  a single clean run does not cover — a precheck that places differently,
  a shuttle-side reharden with different tool versions, and any RTL
  change between now and tape-in. The design has consumed all of it and
  1.70 % more.

The honest reading is that **4x2 is now a run that worked, not a
budget that holds.** `docs/15` section 4.1 already warned that 0.46 %
spare "is not a growth allowance"; the pointer TMR spent it and went
past. There is no headroom left for a further increment, and there are
still open RTL items on the developer list.

### 4.3 The options, and whose decision this is

This is a decision for the owner, and it is time-critical: the shuttle
closes **2026-09-21**, 23 days from this run. The three options named in
the brief, each with the number that bears on it:

1. **Drop to a smaller neuron geometry.** The measured growth factor
   from the pre-fix baseline is now **184,969 / 136,107 = 1.3590,
   +35.9 %** — up from the +33.0 % `docs/15` section 4.5 uses. Re-scaling
   that table's modelled placed areas at +35.9 % **[estimate, a scaled
   model on an unverified model, exactly as `docs/15` cautions]**: 4 x 8
   (32 synapses) needs 217,214 um2 of rows, 8 x 4 needs 236,023 um2 —
   both inside the 259,837 um2 the 4x2 core provides, with 16.4 % and
   9.2 % spare respectively. **A 32-synapse geometry restores real
   margin at 4x2.** It costs half the synapse count, which is a
   demonstrator claim, not a correctness one.
2. **Go to 12 tiles.** 6x2 or 3x4. It removes the problem outright and
   `docs/15` section 4.3 prices the shapes; `docs/15` section 6 also
   records that Tiny Tapeout's own template comment does not list 3x4 as
   a purchasable shape, so 6x2 is the one to price. This is money, and
   the money question is not this document's to answer.
3. **Trim a demonstrator.** 3,083 um2 of placed cell area is what has to
   come out for the design to sit exactly at 70 % — 1.67 % of the
   current placed area **[estimate, arithmetic on measured areas]**. That
   is a small enough number that one non-essential block plausibly covers
   it, and small enough that it will not survive another hardening
   increment.

**What this document does not recommend** is raising the criterion from
70 %. The criterion is what has been carrying the risk that a single
clean run does not, and it has now correctly fired for the first time.
Moving the line because the design crossed it converts a working control
into a formality — the same failure mode `sw/tests/test_synthesis_guards.py`
records for a test bound left where the design was already sitting on it.

A fourth option exists and should be named rather than left implicit:
**accept 71.19 % with eyes open**, on the evidence that the run is clean
on every deck and that the KLayout variant reproduced it to the last
digit. That is defensible only if the RTL is frozen from here, and it
leaves nothing for the shuttle-side reharden. It is a real option and it
is the owner's to take.

---

## 5. sky130: the cross-PDK run no longer routes

`docs/18` section 3.2 states the position this run was meant to update:
"On sky130 neither has: no run exists against that RTL", and section 3.3
asks for one, so that its slack arithmetic stops being quoted on the
`sky-04-tmr` / `tmr-reharden` pair. `sky-08-ptrtmr` is that run.
`sky-04-tmr` predates **three** RTL increments — the `lif_core` memory
ECC, `MIX`, and now the pointer TMR — where the IHP column has been
re-measured at each one.

| Quantity | `sky-04-tmr` (`docs/18` §3.2/3.3) | **`sky-08-ptrtmr`** |
|---|---|---|
| Mapped flip-flops | 1,155 | **1,268** |
| Synthesis cells | 6,470 | **7,634** |
| Synthesis cell area | 80,069.29 um2 | **99,564.24 um2** (+24.3 %) |
| Placed cells, excl. fill | 10,697 | **12,084** |
| **Placed cell area** | 99,923.3 um2 | **123,766 um2** (+23.9 %) |
| Die / core area | 154,113 / 149,183 um2 | **154,113 / 149,183 um2** |
| **Placement utilization** | 66.98 % | **82.96 %** |
| Pointer banks, synthesis netlist | n/a (predates the RTL) | **3 in each of twelve** |
| Detailed routing | converged, **0 DRC** | **did not converge** |
| Magic DRC / KLayout DRC / XOR / LVS / antenna | 0 / 0 / 0 / 0 / 0 | **not reached** |
| Worst setup, `max_ss_100C_1v60` | -2.9659 ns | **not measurable** |

**[fact for `sky-08-ptrtmr` synthesis and placement figures,
`06-yosys-synthesis/reports/stat.json` and the step
`or_metrics_out.json` files; the routing statement is fact and section
5.1 gives the evidence.]**

### 5.1 What "did not converge" means here

TritonRoute's optimization iterations, from the run log:

| Iteration | Violations at end |
|---|---|
| 0th | 218,483 |
| 1st | 348,149 |
| 2nd | still rising when this was written (358,009 at 60 % complete) |

**[fact, `[INFO DRT-0199]` lines in the run log.]** The count is going
**up**, not down, across iterations. This is divergence, not slow
progress, and it is the signature of a design that does not have the
routing resource it needs rather than one the router has not finished
with. The run had spent over 100 minutes in
`44-openroad-detailedrouting` at the time of writing and was still
executing; it never reached `64-magic-drc`, `65-klayout-drc`,
`70-netgen-lvs` or `55-openroad-stapostpnr`, so **no sign-off figure and
no post-route slack exists for this netlist.**

### 5.2 Why, and what it does and does not say

The cause is visible without needing the run to finish. The sky130A 4x2
tile is a different size from the IHP one — `docs/18` section 2.4
records it: 682.64 x 225.76 um against 854.40 x 313.74 um, a
**149,183 um2 core against 259,837 um2**, 57 % of the rows for the same
tile count. The same design that lands at 71.19 % on IHP therefore lands
at **82.96 %** on sky130, against a `PL_TARGET_DENSITY_PCT` of 60. At
`sky-04-tmr`'s 66.98 % it routed clean; at 82.96 % it does not
**[estimate on the causal claim; both utilization figures and both
routing outcomes are fact]**.

What this changes in `docs/18`:

- **The slow-corner miss cannot be re-measured, so its status is
  unchanged and not refreshed.** `docs/18`'s -2.9659 ns on
  `max_ss_100C_1v60` still stands as the last measured sky130 slack,
  still on `sky-04-tmr`, still three RTL revisions old. This run does not
  supersede it and does not confirm it. **The question `docs/18` section
  3.3 leaves open stays open**, and it is now blocked behind a routing
  problem rather than a timing one.
- **`docs/18`'s sign-off row for sky130 is superseded in status, not in
  value.** "0 / 0 / 0 / 0 / 0 on every deck" was true of `sky-04-tmr` and
  is not a statement about the current RTL on sky130.
- **The qualitative portability finding survives and gets stronger.**
  `docs/18` section 6 concludes that portability holds for structure and
  stops at timing. On the current RTL it now stops earlier: at 4x2,
  sky130 does not reach a routed netlist at all. Cross-PDK portability of
  *this design at this tile count* is no longer demonstrated.

None of this bears on the shuttle. The submission target is
ihp-sg13g2 and section 2 is clean. It bears on the portability claim,
which several documents make, and on the NLnet-facing statement that the
design is PDK-independent.

### 5.3 What would settle it, not run here

A sky130 harden at a **larger tile count** — 6x2 sky130 rows are the
comparison that holds utilization roughly constant rather than tile
count, and `docs/18` section 2.4 explains why the project chose to hold
tile count fixed instead. That choice was right for a PDK comparison and
is wrong for the question "can this design be built on sky130", which is
now the live one. Named as a follow-up, not attempted.

---

## 6. Corrections for the integrator

Every entry below is a figure in another document that this run
supersedes. **No document other than this one is edited.** Each row gives
the current text, the replacement, and the source in a `wave5-ihp`,
`ihp-klayoutdrc-w5` or `sky-08-ptrtmr` run directory.

### 6.1 `docs/15-pilot-tile-plan.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| §4.1 table, `ihp-mix` column, mapped flip-flops | 1,235 | **1,268** | `wave5-ihp/06-yosys-synthesis/reports/stat.json` |
| §4.1 table, post-synthesis cell area | 147,649 um2 | **151,556.53 um2** | same |
| §4.1 table, placed standard cells | 181,043 um2 | **184,969 um2** | `wave5-ihp/final/metrics.json` |
| §4.1 table, utilization | 69.6756 % | **71.1867 %** | same |
| §4.1 table, worst-corner setup slack | +0.6315 ns | **+1.1554 ns** | `wave5-ihp/55-openroad-stapostpnr/summary.rpt` |
| §4.1 table, placed instances | 23,763 | **23,584** | `wave5-ihp/final/metrics.json` |
| §4.1 consequence 1, "**The tile budget is settled: 4x2, with 0.46 % of the core spare**" and the sentence "**The pilot fits 4x2 and no further run is needed to say so.**" | as written | **Retract both.** Replacement: at the 70 % criterion the design needs 264,241 um2 of rows against 259,837 um2 available — a shortfall of 4,404 um2, **-1.70 % of the core**. The tile budget is **not** settled and section 4.3 of this document lists the options | §4.1/§4.2 above |
| §4.1 consequence 1, the spare progression "12.99 % … 0.68 % … 0.46 %" | as written | **append**: `wave5-ihp` **-1.70 %** | §4.1 above |
| §4.1 consequence 2, slow corner +0.6315 ns / Fmax 51.6 MHz | as written | **+1.1554 ns**, Fmax **53.1 MHz** | §2.3 above |
| §4.1 consequence 3, "55 flip-flops under each of `u_cfg_a/b/c`" | correct, but witnessed on `ihp-mix` | still 55/55/55, now witnessed on `wave5-ihp`, **and twelve pointer banks at 3 each** | §3 above |
| §4.5 scaling factor, "+33.0 %", "181,043 / 136,107 = 1.3302" | as written | **+35.9 %**, 184,969 / 136,107 = **1.3590** | §4.3 above |
| §4.5 table, 8 x 8 row, "**181,043 [fact]**", "258,633", "**4x2 (8 tiles), 0.46 % spare** — measured" | as written | **184,969 [fact]**, **264,241**, "**4x2 core is 4,404 um2 short at the criterion, -1.70 %** — measured" | §4.1 above |
| §4.5 table, scaled column, other rows at +33.0 % | 212,604 / 231,013 / 306,717 / 342,091 / 443,377 | at +35.9 %: **217,214 / 236,023 / 313,369 / 349,509 / 452,993** | arithmetic, §4.3 above **[estimate]** |
| §4.5, "16 x 16 … the spare there has fallen from 0.3 % to **0.09 %** — 407 um2 of a 443,784 um2 core" | as written | at +35.9 % the 16 x 16 row needs 452,993 um2 against 443,784 um2 — **-9,209 um2, -2.08 %**. It no longer fits 3x4 either **[estimate]** | arithmetic, §4.3 above |
| §4.5, "no row changes shape against the +32.7 % column" | as written | **no longer true**: 8 x 8 leaves 4x2 and 16 x 16 leaves 3x4 at +35.9 % **[estimate]** | same |
| §4.5, "with the memory hardening it is **1,235** against 1,241 declared" | as written | **1,268** mapped; the declared count moves with the pointer TMR and `sw/tests/test_synthesis_guards.py` asserts it rather than hardcoding it | §2.1, §2.2 above |
| §4.6, "`tmr-reharden` closed the slow corner at +6.436 ns, `ihp-memecc` …" progression | as written | **append** `wave5-ihp` **+1.1554 ns** | §2.3 above |

### 6.2 `docs/18-cross-pdk-portability.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| §3.1 sign-off table, sky130A column, all-zero row set | 0 on every deck | **status only**: true of `sky-04-tmr`; **not established on the current RTL** — `sky-08-ptrtmr` did not reach any sign-off deck | §5 above |
| §3.1, ihp-sg13g2 column, "KLayout DRC … *not run*" | as written | **0**, run `ihp-klayoutdrc-w5` | §2.4 above |
| §3.2, "**158,268 um2 at 60.91 %** on ihp-sg13g2 (run `tmr-reharden`)" | as written | latest IHP is **184,969 um2 at 71.1867 %** (`wave5-ihp`); the `sky-04-tmr` / `tmr-reharden` pair remains the only like-for-like one and should stay the quoted ratio | §2.1 above |
| §3.2, "On sky130 neither has: no run exists against that RTL" | as written | a run now exists — `sky-08-ptrtmr`, **123,766 um2 at 82.96 % placement utilization** — but it **did not route**, so it yields no routed area or sign-off figure | §5 above |
| §3.2, "sky130 sits **6.1 points above** the IHP utilization" | as written | unchanged as a statement about the `sky-04-tmr` / `tmr-reharden` pair; on the current RTL the placement utilizations are **82.96 % sky130 against 71.19 % IHP, 11.8 points above** **[estimate]** | §5 above |
| §3.3, IHP reference table (+6.4359 / +11.4227 / +14.1670) | as written | still correct for `tmr-reharden`; current IHP is **+1.1554 / +8.0521 / +12.1355** (`wave5-ihp`) | §2.3 above |
| §3.3, "the IHP column has since moved twice and the sky130 column has not moved at all" | as written | the IHP column has now moved **three** times; the sky130 column still has not, and §5 explains why it could not | §5 above |
| §3.3, "should stay that way until a sky130 run exists on the current RTL" | as written | a sky130 run on the current RTL was attempted and **does not route at 4x2**; the instruction stands and the condition is **not** met | §5 above |
| §3.3, frequency table, ihp column "20 - 6.4359 = 13.564 ns -> 73.7 MHz" | as written | current IHP slow-corner path **18.845 ns -> 53.1 MHz** **[estimate]** | §2.3 above |
| §6 / §1048, portability conclusions | "portability holds for structure, stops at timing" | on the current RTL it stops **earlier**: at the 4x2 tile count sky130 does not reach a routed netlist | §5.2 above |

### 6.3 `docs/20-reharden-and-corners.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| Headline, "1,155 flip-flops, 158,268 um2 … 60.91 % … **+6.436 ns**" | as written | **1,268 / 184,969 um2 / 71.1867 % / +1.1554 ns** | §2.1, §2.3 above |
| Headline, "**4x2 still fits, with 13.0 % of the core spare**" | as written | **retract**: **-1.70 %**, over budget by 4,404 um2 | §4.1 above |
| §2.1 sign-off table, every `tmr-reharden` value | as written | replaced column by column by the `wave5-ihp` column of §2.1 above | `wave5-ihp/final/metrics.json` |
| §2.1, "1,155 - 1,045 = 110, exactly the two banks" | as written | still the correct account of the configuration domain; the pointer domain adds **+24** and `pilot_top` **+9**, total **1,268** | §2.2 above |
| §2.2 timing table | +6.436 / +11.423 / +14.167 | **+1.1554 / +8.0521 / +12.1355** | §2.3 above |
| §2.2, "a post-route slow-corner Fmax of about **73.7 MHz**" | as written | **53.1 MHz** **[estimate]** | §2.3 above |
| §2.3, "**KLayout DRC did not run**" and §9 item 1 | as written | closed for the current netlist: **0**, `ihp-klayoutdrc-w5` | §2.4 above |
| §2.4, the whole fit calculation — "226,097 um2 … **13.0 % of the core area spare** … consumes **87.0 %** of the budget" | as written | **264,241 um2 needed, -4,404 um2 spare, -1.70 % of the core, 101.70 % of the budget consumed** | §4.1 above |
| §2.4, "the decision does not change — 4x2 was and remains the minimum shape" | as written | **the decision does change**: 4x2 is no longer sufficient at the criterion. §4.3 above lists the options | §4.2 above |
| §2.4, the 8 x 16 row estimate "lands near 268,000 um2 … treated as 6-tile" | as written | at +35.9 % it lands at **313,369 um2 of rows needed**; 6-tile remains wrong and it is a **12-tile** row **[estimate]** | §4.3 above |
| §4 table, sky130 `sky-04-tmr` column | as written | not superseded — `sky-08-ptrtmr` produced no routed figures to replace it with; see §5 above for its status | §5 above |
| §8.1, "107,782 um2 … **126,647 um2**" substitution row | as written | current post-synthesis cell area is **151,556.53 um2** | §2.1 above |
| §8.2 / §8.3 correction lists | as written | extend with §6.2 of this document | — |
| §9, "what is not done" | as written | the KLayout item is closed (§2.4); a **sky130 harden at a larger tile count** is a new open item (§5.3) | — |

### 6.4 `docs/21-pilot-datasheet.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| §7.1 table, "Mapped flip-flops 1155 `sg13g2_dfrbpq_1` [measured, in flux]" | as written | **1268 `sg13g2_dfrbpq_1`** — and the tag can move from **[measured, in flux]** to **[measured]** for `c5a5a6e` | `wave5-ihp/06-yosys-synthesis/reports/stat.json` |
| §7.1 table, "of which configuration TMR, 55 in each of three banks" | as written | correct; **add** a row: "of which AER pointer TMR, **3 in each of twelve banks**" | §3 above |
| §7.1 source path `tt/runs/tmr-reharden/…` | as written | **`tt/runs/wave5-ihp/…`** throughout | — |
| §7.1, "worst setup slack +6.4359 ns … worst hold slack +0.1192 ns" | as written | **+1.1554 ns** setup on the slow corner, **+0.1093 ns** hold on the fast corner | `wave5-ihp/55-openroad-stapostpnr/summary.rpt` |
| §7.1, "The re-harden in progress closes all three IHP PVT corners" | as written | it is no longer in progress; `wave5-ihp` is complete and closes all three | §2.3 above |
| §7.1, verification status "152 passed, 1 skipped — including the eight synthesis guards" | as written | the synthesis-guard file is now **17 passed, 0 skipped**; the skipped test was `test_pointer_tmr_survives_the_real_hardening_flow` and it now passes. The whole-suite count should be re-run rather than adjusted by hand | §3 above |
| §7.2, the entire "Figures that are in flux" table | 1155 / 126,647 / 158,268 / 60.9 % / +6.4359 ns | **1268 / 151,556.53 um2 / 184,969 um2 / 71.19 % / +1.1554 ns** | §2.1, §2.3 above |
| §7.2, "Total power at 50 MHz, typical — not yet re-measured" | as written | **5.119 mW** (4.214 internal + 0.898 switching + 0.006 leakage) | `wave5-ihp/final/metrics.json`, `power__total` |
| §7.2, "Utilization of the 4x2 block … **60.9 %** still well inside the tile" | as written | **71.19 %**, and **not** inside the 70 % planning criterion — §4 above | §4.1 above |
| §7.2, "DRC, LVS and antenna results for the current netlist are **pending**" | as written | complete and all zero, **including KLayout DRC** | §2.1, §2.4 above |
| §6.3, the configuration-TMR correction | as written | still correct; **add** the pointer-TMR case, which is the same failure mode caught before tape-out rather than after — §3 above | §3 above |

---

## 7. What is not done

1. **The sky130 4x2 route.** `sky-08-ptrtmr` was still executing in
   `44-openroad-detailedrouting` when this was written, with a rising
   violation count. It should be allowed to terminate and its final
   state recorded, but the placement utilization of 82.96 % is already
   the answer and a converged route at that density is not expected.
2. **A sky130 harden at 6x2**, which is the run that would say whether
   the design is buildable on sky130 at all. Section 5.3.
3. **The tile decision itself.** Section 4.3 lists the options and the
   numbers that bear on each. It is the owner's call and the shuttle
   closes 2026-09-21.
4. **Gate-level simulation against this netlist.** `docs/20` section 8.1
   already flags the smoke test as stale against `tmr-reharden`; it is
   staler now. `tt/runs/wave5-ihp/final/nl/` is the netlist to re-run it
   against.
5. **Whole-suite verification counts.** Only
   `sw/tests/test_synthesis_guards.py` was run here (17 passed). The
   `docs/21` section 7.1 figure of "152 passed, 1 skipped" should be
   re-derived rather than patched.
6. **No power analysis with annotated activity.** The 5.119 mW of
   section 2.1 is the flow's own estimate from defaults.

---

## 8. Reproducing this

```bash
make -f tools.mk toolcheck

# Pin the RTL so a concurrent hw/rtl edit cannot change the run
# under it (docs/20 section 1.2). Each prints the blob it wrote.
python3 hw/openlane/pin_rtl.py c5a5a6e tt/src/config_merged.json                    /tmp/pin-ihp-w5
python3 hw/openlane/pin_rtl.py c5a5a6e hw/openlane/pilot_sky130/config.json         /tmp/pin-sky-w5
python3 hw/openlane/pin_rtl.py c5a5a6e hw/openlane/pilot_ihp/config.klayoutdrc.json /tmp/pin-ihpdrc-w5

# Section 2 -- the IHP sign-off, submission config, into tt/runs/ so
# that sw/tests/test_synthesis_guards.py can see it.
mkdir -p tt/runs/wave5-ihp
CONFIG=/tmp/pin-ihp-w5/config.json hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag wave5-ihp --force-run-dir $PWD/tt/runs/wave5-ihp

# Section 2.4 -- the KLayout deck, and the determinism control
mkdir -p hw/openlane/pilot_ihp/runs/ihp-klayoutdrc-w5
CONFIG=/tmp/pin-ihpdrc-w5/config.json hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag ihp-klayoutdrc-w5 \
    --force-run-dir $PWD/hw/openlane/pilot_ihp/runs/ihp-klayoutdrc-w5

# Section 5 -- sky130
mkdir -p hw/openlane/pilot_sky130/runs/sky-08-ptrtmr
CONFIG=/tmp/pin-sky-w5/config.json hw/openlane/pilot_sky130/run_sky130.sh \
    --run-tag sky-08-ptrtmr \
    --force-run-dir $PWD/hw/openlane/pilot_sky130/runs/sky-08-ptrtmr

# Section 3 -- the guard
.venv/bin/python -m pytest sw/tests/test_synthesis_guards.py -v

# Every table above
python3 hw/openlane/signoff_report.py tt/runs/wave5-ihp \
    hw/openlane/pilot_ihp/runs/ihp-klayoutdrc-w5 \
    hw/openlane/pilot_ihp/runs/ihp-mix
```

`--force-run-dir` is a hidden LibreLane 3.0.5 option
(`librelane/flows/cli.py`); without it a run lands in
`<config-dir>/runs/<tag>`, which for a pinned config is the disposable
snapshot directory.

`tt/runs/` and `hw/openlane/*/runs/` are gitignored. The `pin_rtl.py`
snapshots are disposable and regenerable from `c5a5a6e`; the blob table
in section 1.2 is the record, not the path.
