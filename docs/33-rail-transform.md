# 33 — What the dual-rail storage transform actually reaches

Status: complete, and it is a correction rather than a fix. The three
dual-rail flag modules — `pilot_flag_rail` in `hw/rtl/pilot_top.v`,
`aer_flag_rail` in `hw/rtl/aer_fifo.v`, `lif_flag_rail` in
`hw/rtl/lif_core.v` — each claimed two independent defences against
synthesis merging the pair into one flip-flop: the `keep` attributes,
and a per-rail storage polarity that "depends on no attribute". The
second defence **is real and is measured here for the first time**, but
it **does not reach the shipped netlist**: `dfflibmap` erases it during
technology mapping, and every rail in
`hw/openlane/pilot_ihp/runs/signoff-6x2/final/nl/` stores the flag in
true polarity with no inverter anywhere. The headers described the
transform as if the netlist carried it. It does not.

**No RTL logic changed.** What changed: the headers of the three rail
modules, and `sw/tests/test_synthesis_guards.py`, which now asks the
attribute-free question with the attributes actually deleted and counts
the rails in the shipped netlist rather than only in a model of it.

Convention, inherited from `docs/18`, `docs/22` and `docs/27`:
**[fact]** = measured in this environment or read out of an installed
file; **[estimate]** = derived or judged.

Toolchain: the pinned checkout, `make -f tools.mk toolcheck` reporting
`yosys 0.67+146` at
`~/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite` [fact].
Liberty: `sg13g2_stdcell_typ_1p20V_25C.lib` from the ciel
`ihp-sg13g2` checkout `c4b8b4e5` [fact].

### Headline

- **The rails in the sign-off netlist are two identical flip-flops.**
  Eight rails, one `sg13g2_dfrbpq_1` each, the POL=1 rails carrying
  buffers where the RTL asked for inverters and no inverter anywhere
  [fact].
- **`dfflibmap` is what erased the polarity, not `opt_expr`.** The rail
  stores `1'b0 ^ POL` at reset, so the POL=1 rail is a flip-flop that
  resets to 1, and this library gives `dfflibmap` nothing that does
  that. It prints `unmapped dff cell: $_DFF_PN1_` and builds the cell by
  inverting D and Q around a reset-to-0 flop; those inverters meet the
  rail's own `d ^ POL` and `bits ^ POL`, and `abc` folds each pair to a
  buffer [fact].
- **The transform nevertheless does its job.** With every `(* keep *)`
  and `(* keep_hierarchy *)` deleted from the text of `hw/rtl`, both
  synthesis recipes keep all **1,296** flip-flops — no rail merged, no
  bank merged. Removing the transform from `pilot_flag_rail` collapses
  the pair to one flip-flop in the same conditions [fact].
- **The erasure is safe in this flow and would not be in another.**
  `dfflibmap` runs after the last pass that can merge anything, so it
  cannot cause the collapse `POL` exists to prevent. But a flow with a
  merge pass after mapping would see two identical cells, and only the
  attributes and the census would be standing there.
- **No portable RTL fixes this at one bit** [estimate, from a proof
  given in section 5]. The correction cannot be moved out of the module
  to escape the fold, because what folds against it is added by
  `dfflibmap` on the same two combinational cones.

---

## 1. What the headers claimed

`pilot_flag_rail`, before this document:

> `POL` — the per-rail storage transform. One rail stores the flag and
> the other stores its complement, so the two flip-flops present
> different (D, EN, reset) signatures and structural hashing has nothing
> to match with the hierarchy gone.

and, in `pilot_cfg_bank` from which the rails were cut down, the phrase
that made it a promise about the artifact: *"Plain Verilog-2005; depends
on no attribute."*

Two claims are packed together there and only one of them is true:

1. the two rails are structurally distinct **where merging happens** —
   true, and section 4 measures it;
2. the two rails are structurally distinct **in the netlist** — false,
   and section 2 measures that.

This matters for the reason `docs/20` section 11 gives about bounds a
design is already sitting on: the configuration TMR survived a review
because a check was read as confirming something it could not
distinguish. A header that describes a defence the artifact does not
contain is the same defect one level up.

## 2. What the sign-off netlist contains

Cells whose instance path lies under each rail, counted in
`hw/openlane/pilot_ihp/runs/signoff-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v`
[fact]:

| rail | POL | cells |
| --- | --- | --- |
| `u_pilot.u_ohv_a` | 0 | 1 × `sg13g2_dfrbpq_1` |
| `u_pilot.u_ohv_b` | 1 | 1 × `sg13g2_dfrbpq_1`, 2 × `sg13g2_buf_1` |
| `u_pilot.u_evq_in.u_rdv_a` | 0 | 1 × `sg13g2_dfrbpq_1` |
| `u_pilot.u_evq_in.u_rdv_b` | 1 | 1 × `sg13g2_dfrbpq_1`, 2 × `sg13g2_buf_1` |
| `u_pilot.u_evq_out.u_rdv_a` | 0 | 1 × `sg13g2_dfrbpq_1` |
| `u_pilot.u_evq_out.u_rdv_b` | 1 | 1 × `sg13g2_dfrbpq_1`, 2 × `sg13g2_buf_1` |
| `u_pilot.u_lif.u_op_a` | 0 | 1 × `sg13g2_mux2_1`, 1 × `sg13g2_dfrbpq_1` |
| `u_pilot.u_lif.u_op_b` | 1 | 1 × `sg13g2_mux2_1`, 1 × `sg13g2_buf_1`, 1 × `sg13g2_dfrbpq_1` |

`sg13g2_dfrbpq` is the reset-to-0 flip-flop: `clear : "RESET_B'"`,
`next_state : "D"`, no preset [fact, read out of the liberty]. **There is
no inverter in any of the eight instances.** Both rails of every pair
store the flag in true polarity, and the `_b` rails differ from the `_a`
rails only by buffers — which are drive and hold fixing, not function.
The `lif` pair carries an extra `mux2` each because that rail has an
enable; the mux is present on both sides and identical.

For contrast, and because it is what makes the mechanism legible, the
55-bit configuration replica in the same netlist [fact]:

| bank | cells |
| --- | --- |
| `u_pilot.u_cfg_a` | 55 × `dfrbpq`, 51 × `mux2`, 55 × `buf`, 4 × `inv`, … |
| `u_pilot.u_cfg_b` | 55 × `dfrbpq`, **55 × `inv`**, 51 × `nand2`, 51 × `o21ai`, … |
| `u_pilot.u_cfg_c` | 55 × `dfrbpq`, 25 × `inv`, 73 × `xnor2`, 37 × `xor2`, … |

Replica B kept its polarity: `nand2`/`o21ai` where A has `mux2`, and an
inverter on every output. The rails did not. Section 3 says why the same
`POL` layer survives at 55 bits and not at one.

## 3. Why: `dfflibmap` has no reset-to-1 flip-flop to give it

The rail is six lines:

```verilog
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) bits <= 1'b0 ^ POL;
    else        bits <= d ^ POL;
end
assign q = bits ^ POL;
```

so the **stored reset value is `POL` itself**. With `POL = 1` the rail is
a flip-flop that comes out of reset holding 1, which yosys represents as
`$_DFF_PN1_` (or `$_DFFE_PN1P_` for the `lif` rail, which has an enable).

`dfflibmap` against the sign-off liberty reports [fact]:

```
cell sg13g2_dfrbpq_1 (noninv, pins=4, area=48.99) is a direct match
    for cell type $_DFF_PN0_.
    ...
    unmapped dff cell: $_DFF_PN1_
```

The library is not empty of set-capable storage — `sg13g2_sdfbbp_1`
carries `SET_B` alongside `RESET_B`, `SCD` and `SCE` [fact] — but
`dfflibmap` does not take a scan cell for a plain flip-flop, so the only
asynchronous flip-flop available to it resets to 0. It therefore
implements `$_DFF_PN1_` the standard way: store the complement in a
reset-to-0 cell and put an inverter on D and an inverter on Q.

Those inverters land on the same two combinational cones as the rail's
own. On the D side, `~d` from the RTL meets `~` from `dfflibmap`; on the
Q side, `~bits` from the RTL meets `~` from `dfflibmap`. `abc` maps each
double inversion to a buffer, and the rail is a plain flip-flop again.

Reproduced in isolation, with both attributes deleted from the source, a
harness holding one POL=0 and one POL=1 `pilot_flag_rail` [fact]:

| after | cells |
| --- | --- |
| `synth -flatten` | 1 × `$_DFF_PN0_`, 1 × `$_DFF_PN1_`, `$_NOT_`, `$_XNOR_`, `$_ANDNOT_` |
| `dfflibmap`, `abc` | 2 × `sg13g2_dfrbpq_1`, 1 × `sg13g2_buf_1`, `and2`, `xor2` |

Two flip-flops either way — and structurally distinct on the first line,
identical on the second.

**Why `u_cfg_b` escapes.** Two reasons, and both are accidents of width
rather than of design. The configuration bank resets to a non-zero
default, so `RESET_VALUE ^ POL` is 0 on some bits and 1 on others and
only the latter are re-inverted; and its D cone is an enable mux rather
than a bare wire, so where `dfflibmap`'s inverter is absorbed it is
absorbed into a *different gate* (`nand2`/`o21ai` instead of `mux2`)
rather than annihilating with a matching inverter. The `lif` rail shows
that the enable alone is not enough: `u_op_b` has the mux and still
folded, because its reset value is uniformly 1 and its correction is a
matching inverter.

## 4. What the transform does buy, measured

The existing attribute-free guards strip `keep_hierarchy` with `attrmap`
after elaboration and leave `(* keep *)` on the storage, so they were
measuring `POL` **plus** one of the two hints. `sw/tests/test_synthesis_guards.py`
section 1e now deletes the *text* of both attributes from a copy of
`hw/rtl` before yosys reads it, which no pass can honour and none can
re-derive.

Design-wide flip-flop population, both recipes [fact]:

| sources | ASIC recipe | `synth_ecp5` |
| --- | --- | --- |
| as committed | 1,296 | 1,296 |
| every `keep` and `keep_hierarchy` deleted | 1,296 | 1,296 |

Nothing is lost. Not one rail, not one of the 165 configuration replica
bits, not one of the 36 pointer replica bits. The per-replica storage
transforms carry the whole design on their own.

Mutation-checked twice, because the design-wide test and the per-module
harness answer to different mutations and each passes the other's [fact]:

| mutation | effect |
| --- | --- |
| `.POL(1'b1)` → `.POL(1'b0)` on the `u_ohv_b` **instantiation** | both totals 1,296 → 1,295; `test_no_flip_flop_is_lost_when_every_attribute_is_deleted` fails |
| `bits <= d ^ POL` / `q = bits ^ POL` → `bits <= d` / `q = bits` inside `pilot_flag_rail` | the pilot harness maps to 1 flip-flop; `test_a_rail_pair_is_two_flip_flops_with_no_attribute_at_all[pilot_top.v]` fails |

Neither mutation is visible to any simulation in this repository. Both
are functionally identical RTL; the first is identical bit for bit at
every port.

**So the claim "depends on no attribute" is true.** What was wrong was
the sentence that followed it, which described the flip-flops in the
netlist.

## 5. Why it cannot be made to reach the netlist

The obvious repair is to stop cancelling the polarity inside the module
— have the rail present `bits` raw and let the consumer apply `^ POL` —
on the theory that a correction in the parent cannot fold against a
transform in the child. It does not work, and the reason is section 3:
the inverters that fold against the rail's are not the rail's own, they
are `dfflibmap`'s, and `dfflibmap` adds them to whichever cone the
correction happens to sit in. Moving the XOR one level up moves the fold
one level up with it.

The deeper bound is the one `docs/20` and `hw/rtl/pilot_top.v` section
8.2 already prove for the third replica, applied to the second:

- over one variable there are exactly two storage functions, `x` and
  `~x`, so a second rail that is not a copy **must** store `~x`;
- a rail storing `~x` for a flag whose safe value is 0 **must** hold 1
  after reset — that is what `~0` is;
- this library has no asynchronous flip-flop that holds 1 after reset
  that `dfflibmap` will use, so that cell is always built by inversion,
  and the inversion always meets the correction that turns `~x` back
  into `x` somewhere in the same two cones.

A time-varying mask (store `d ^ tick`, correct with `^ tick`) does leave
a structurally distinct D cone that survives mapping, and it is rejected
on two grounds: `lif_flag_rail` holds its bit across many cycles behind
an enable, so undoing a mask that moved in the meantime needs the mask
value remembered alongside the bit; and `tick` would be new unprotected
state whose own upset produces a false mismatch, which for these
consumers means a dropped event. Adding an unprotected single point to
defend a structure that the census already covers is the wrong trade
[estimate].

The conclusion is not "the rails are unprotected". It is that **for a
one-bit rail in this PDK the netlist-level structural difference is not
available**, the same way a third replica of a one-bit flag is not
available, and the honest thing is to say so where the reader is
standing.

## 6. What is now checked

`sw/tests/test_synthesis_guards.py`, section 1e and the netlist census
below it:

| test | what it fails on |
| --- | --- |
| `test_a_rail_pair_is_two_flip_flops_with_no_attribute_at_all[pilot_top.v \| aer_fifo.v \| lif_core.v]` | the transform removed or weakened inside any of the three rail modules |
| `test_no_flip_flop_is_lost_when_every_attribute_is_deleted` | any structure in the design that only an attribute is holding, rail or bank |
| `test_the_shipped_netlist_holds_one_flip_flop_per_rail` | a rail that merged in the artifact the shuttle receives |

The last one is the one that makes the erasure in section 2 tolerable,
and it deliberately asserts nothing about the *other* cells in each
instance. A future PDK with a set flop would leave the inverters
standing; that is an improvement, and a test that failed on it would be
recording the tool rather than the design — `docs/20` section 11 again.

## 7. Re-run, because the RTL files changed even though the logic did not

The three rail modules' headers are comments, so nothing this document
touches can move a gate. That is an argument, and the suites were run
anyway [fact], with the pinned toolchain:

| gate | result |
| --- | --- |
| `sw/tests` (whole tree) | 230 passed, including the 40 in `test_synthesis_guards.py` |
| `hw/tb` pilot suite | 31 passed |
| `hw/tb` aer_fifo suite | 20 passed |
| `hw/tb` lif lockstep suite | 32 passed |
| `formal` `prove`, `prove_d4`, `bmc`, `cover` | 4 PASS; `prove` and `prove_d4` both by k-induction |
| `hw/tb` fault-injection campaign | 378 injections, identical classification target by target to the committed log |

The campaign: 97 MASKED, 193 CORRECTED, 82 DETECTED, 6 SDC, 0 HANG, and
**14 of 14 rail injections DETECTED** with none silent — the same
numbers, the same targets and the same classes as before, so the only
line that moved in `hw/tb/fi_campaign_results.json` is `wall_seconds`,
443.1 → 445.7. The gate-level campaign was **not** re-run: it injects
into the `signoff-6x2` netlist, which no comment can change.

## 8. What is stale after this document

- `hw/openlane/pilot_ihp/runs/signoff-6x2` **predates the header edits**
  in the three rail modules. The edits are comments only, so the netlist
  is unaffected in substance, but the run's RTL commit is no longer this
  tree's HEAD. Nothing in this document asks for a re-harden.
- `sw/tests/test_synthesis_guards.py` section 1c records a mutation
  measurement of `1274 → 1273` from 2026-08-30. That total is from a
  smaller tree and is not reproducible today; section 1e carries the
  current pair, `1296 → 1295`.
