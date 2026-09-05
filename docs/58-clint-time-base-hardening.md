# 58 — The clock is a counter, so it does not need a second copy of itself

`docs/41-watchdog-hardening.md` section 7.4 ranked `mtime` above
everything the watchdog wave left unprotected, and then did not protect
it. `docs/43-core-hardening.md` section 12 ranked it second and did not
protect it. `docs/44-margin-and-observability.md` section 3 ranked it
first, wrote *"it is not started, not partly built, and not in this
document's file list"*, and did not protect it. Three deferrals, each
correct on its date, and the reason is always the same one: an upset in
`mtime` is **persistent and silent** — it displaces the architectural
clock for ever, and every deadline software computes as `mtime + delta`
is then wrong — but it **cannot disarm anything**, so the backstop went
first.

The backstop is protected (`docs/41`). The core's register file is
protected (`docs/43`). The connection to the NPU is protected
(`docs/55`, `docs/56`). This is what is left, and this document builds
it.

**The answer is not triple modular redundancy, and the reason is the
one `docs/41` section 7.4 pointed at without designing:** `mtime`
increments by one every tick, so it has structure a general register
does not, and that structure makes the counter *checkable and
repairable* without a second copy of the data. What `docs/41` got wrong
was not the direction but the currency — it priced the cheap answer in
flip-flops, where the cost of a check over a 64-bit counter is the
reduction tree and not the shadow register. Section 4 is that argument
with six synthesised designs behind it.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **What was built?** | **H6: `mtime` is the 64-bit data field of a (72,64) SECDED codeword, decoded and corrected on every tick, with the corrected value driving the counter, the comparator and every bus read.** Eight added flip-flops. `hw/rtl/secded_enc.v` and `secded_dec.v` are read in place, not copied. Section 3 |
| **Does it correct or only detect?** | **Correct.** 144 of 144 single-bit injections into the 72 stored bits came back CORRECTED with the clock unchanged at every port and the deadline on its golden cycle **[fact]**. Against the same 128 draws the unprotected design displaced the clock in 95 and announced none. Section 8 |
| **What does it cost?** | **+7,026.8310 um2 and +8 flip-flops on the CLINT — +42.04 % of the block and +2.549 % of the Ibex core [fact]**, plus **+1,917.4050 um2 and +18 flip-flops** on `soc_busstat` for the report. Section 7 |
| **Was the residue check the cheap answer `docs/41` said it was?** | **No, and this is the document's own negative result. Measured, a residue-mod-3 detector costs 98.694 % of what the corrector costs and corrects nothing** **[fact, two synthesised designs]**. `docs/41` priced it in flip-flops — 2 against 8 — and the flip-flops are not where the money is. Section 4.3 |
| **Was `docs/41`'s +27,000 um2 estimate for TMR right?** | **Yes, to within 4.68 %. Measured: +25,792.0740 um2 and exactly +256 flip-flops** **[fact]**, against an estimate of "roughly +27,000 um2 ... 256 more flip-flops" made with nothing synthesised. The estimate is now a measurement. Section 4.4 |
| **Are the upper bits architecturally dead, and does that mean protecting them is protecting nothing?** | **Dead, yes — 11 of the 64 over a five-year mission at the 20 ns sign-off period. And the conclusion is the opposite of the one offered.** Deadness bounds the *fault-free* value and says nothing about the faulty one: the dead bits carry the largest displacement in the design (bit 63 is 5,845 years) and are the cheapest to cover. Truncating to 54 bits is measured at **−1,438.1766 um2** and leaves bit 53 at 5.7 years, which still ends the mission. Section 4.5 |
| **Is `mtimecmp` the same problem?** | **No, and it gets nothing.** It fails `docs/41` section 3.1's criterion on both halves, and the campaign measures it: **128 injections displaced the clock zero times**; 60 of them removed the deadline entirely, which is a missed deadline, which is the exact failure the watchdog is the backstop for. Section 6 |
| **What is the recovery when detection is all there is?** | Named rather than assumed, because a detector with no recovery is a fault channel. For the correctable case there is nothing to recover from. For the uncorrectable case the recovery is a **re-epoch**, and the SoC already contains the second time base it needs: at `TICK_DIV = 1`, `mcycle` advances at exactly `mtime`'s rate. Section 5 |
| **Is the whole-SoC invariant still 215,428 cycles?** | **Yes, exactly. 27 checks, fail mask 0** **[fact]**. This wave changes no software, so there is one measurement and not three. Section 8.4 |
| **What did it cost to prove?** | The honest number and it is large: the `soc_clint` bounded check went from **6 s to 18 min 19 s** and the k-induction proof from **2 s to 5 min 57 s** **[fact]**. A 64-bit counter with a 64-bit XOR-tree invariant over it is a hard SMT problem. Section 9.3 |

---

## 2. What `mtime` is in this design, and what an upset in it does

`docs/40-interrupts-timers-watchdog.md` section 4 settles why the CLINT
and the GPTIMER both exist and it is worth restating, because the
division of labour is what makes this block's failure mode the one it
is:

> **CLINT owns time.** `mtime` is a free-running 64-bit up-counter that
> is never reloaded and never restarted … It is the only time base with
> an architectural meaning … **GPTIMER owns intervals.** Its timers
> count *down* from a reload value and restart.

A down-counter that reloads sheds an upset on its own: `docs/41` section
7.1 measured the watchdog's `counter` doing exactly that, worst single
deadline moved 512 clocks against a 1,024-clock bound, all sixteen
injections ending in the identical final state. **An up-counter that
never reloads sheds nothing.** There is no event in the mission that
rewrites `mtime` with a correct value, so a flip in bit *i* adds or
subtracts 2^*i* ticks and that offset is carried for the rest of the
mission.

At the 20 ns period `docs/47`'s sign-off run and `docs/53` section 7 both
use, and at `TICK_DIV = 1` — which is how `soc_top.v` instantiates the
block, so one tick is one CPU clock:

| flipped bit | displacement | in mission time |
|---:|---:|---|
| 0 | 1 tick | 20 ns |
| 20 | 2^20 ticks | 21.0 ms |
| 32 | 2^32 ticks | **85.9 s** |
| 40 | 2^40 ticks | **6.11 hours** |
| 48 | 2^48 ticks | **65.2 days** |
| 53 | 2^53 ticks | **5.71 years** |
| 63 | 2^63 ticks | **5,845 years** |

**[estimate, arithmetic on the 20 ns SDC period; the period is a fact,
`docs/53` section 7]**

Two things follow and they shape everything below.

**The consequence curve is smooth and it is exponential.** There is no
bit at which `mtime` stops mattering and none at which it starts. That
is why the graded answer — protect the top half, leave the bottom —
is not obviously right, and why an answer that covers all 64 bits for
one price is worth more than its bit count suggests.

**The failure is silent in the precise sense `docs/41` section 3.1
means.** A wrong `mtime` does not stop the timer interrupt; it goes on
firing, on the wrong dates. `docs/40` section 10 item 2 calls it "a
silently wrong clock" and the campaign in section 8 is what turns that
phrase into a number: in the unprotected design, **95 of 128 injections
displaced the clock and not one of them was announced by anything**.

### 2.1 The 163 flip-flops, itemised

`docs/40` section 9 measured `soc_clint` at 163 flip-flops and this
document needs the breakdown, because four of the five items in it are
deliberately left alone:

| | flip-flops | H6 |
|---|---:|---|
| `mtime` | 64 | **protected** |
| `mtimecmp` | 64 | not, section 6 |
| `msip` | 1 | not, section 9.1 |
| `rdata_o` | 32 | not, section 9.1 |
| `rvalid_o`, `err_o` | 2 | not, section 9.1 |
| `tick_cnt` | 0 | dead at `TICK_DIV = 1` |
| **total** | **163** | |

`tick_cnt` is declared 32 bits wide and is not there. At `TICK_DIV = 1`
the `if (TICK_DIV > 1)` branch never elaborates a driver, `tick` is the
constant 1, and the optimiser removes the register — which is why
`docs/40` measured 163 and not 195. It is stated because a reader
counting the declarations gets a different number, and because it means
there is no prescaler in this configuration to protect or to leave
alone.

---

## 3. What was built

### 3.1 The mechanism, in one paragraph

`mtime` is held as the data field of a (72,64) SECDED codeword whose
eight check bits are the only added state. Every tick the stored word is
**decoded**; the corrected 64-bit value is what increments, what the
`mtime >= mtimecmp` comparator sees and what a bus read of `MTIMEL` or
`MTIMEH` returns; and the check bits are **re-encoded over the value
that goes back in**, not over the value that was stored.

That last clause is the whole design. Encoding over the stored value
instead is the standard way to build an ECC counter that silently does
nothing: the code follows the corruption into consistency on the next
edge, the word becomes a valid codeword over a wrong value, and the
upset is never seen and never repaired. Section 9.4 is the textual
guard that the two are the right way round, and it exists because **no
census, no proof and no functional test outside the campaign in this
repository can tell the two apart**.

### 3.2 Three consequences, and the third is why this is cheap

1. **A single-bit upset anywhere in the 72 bits — data or check — is
   corrected before it reaches any port.** `mtip` never asserts early, a
   bus read never returns the corrupt word, and the counter goes on from
   the right value. That is the guarantee TMR gives, on 8 added
   flip-flops instead of 128.
2. **A double-bit upset is detected and never miscorrected**, because
   every column of `secded_enc.v`'s H matrix has odd weight, so a
   two-bit error always produces a nonzero *even*-parity syndrome, which
   can never equal a column. The block cannot repair it — the
   information is gone — and it says so.
3. **THE COUNTER SCRUBS ITSELF.** A code over a register written once in
   a mission needs a scrubber, because errors accumulate until something
   rewrites the word; `docs/43` built one for the register file and
   section 6.4 of that document left its period unbounded, which is the
   one thing `BUSSTAT.CNT_RFRD` exists to make observable. `mtime` is
   rewritten **every clock by construction**, so the scrub period here
   is one cycle, there is no scrubber to build, no period to choose and
   no accumulation to bound. The window in which a second upset could
   turn a correctable word into an uncorrectable one is **20 ns wide**.

Consequence 3 is not an incidental nicety. It is the reason the
uncorrectable class is empty under this repository's fault model, and
that emptiness is what section 9.2 spends the last BUSSTAT bit on the
strength of.

### 3.3 The codec is read and not copied

`hw/rtl/secded_enc.v` and `hw/rtl/secded_dec.v` are **fixed at 64 data
bits and 8 check bits by an elaboration guard in each file**, and 64 is
exactly `mtime`'s width. No width parameter is passed and none could be.
They are read out of `hw/rtl/`, which `docs/34-pilot-freeze.md` pins by
git blob hash for the TTIHP26b shuttle, in the same way
`ibex_regfile_secded.v` already reads them (`docs/43`) and `soc_wdog.v`
reads `tmr_voter.v` (`docs/41`). **Nothing in `hw/rtl/` is modified by
this work.**

The consequence worth naming: the code itself is proved once, for every
consumer, in `formal/secded.sby`, and cross-checked against
`sw/golden/secded.py` in `hw/tb/test_secded.py`. This document does not
re-prove it and does not claim to. What it proves is that *this block*
keeps the stored word a codeword (section 9.3, E1) and that the codec is
invisible when it is (E2).

### 3.4 The report, and the one bit that was left

`mt_ecc_o` is one cycle high whenever the stored codeword was not a
codeword. It is one cycle per event **by construction and for a reason
no other fault line in this SoC has**: the word is re-encoded on every
edge, so a syndrome that is nonzero this cycle is zero the next, whether
it was correctable or not.

It goes to `soc_busstat.v`, and it had to, because **there is no free
offset in a standard CLINT window to put a status register at**. The
architectural layout spends `0x0000`–`0x3FFF` on the `msip` array,
`0x4000`–`0xBFF7` on the `mtimecmp` array and `0xBFF8`–`0xBFFF` on
`mtime`; every offset this block currently faults on is spoken for by a
hart that does not exist. Inventing a status register there would make a
multi-hart-aware driver's probe of some hart return telemetry, which is
worse than the bus error `soc_clint.v`'s header argues for.

In BUSSTAT it takes bit 7 — **the last bit below the interrupt bit**.
`soc_busstat.v`'s read multiplexer has carried a comment since `docs/55`
saying that bit 8 is the interrupt and stays at bit 8 "so the sticky
field grows UP TO bit 6 and the gap between them shrinks rather than the
interrupt moving". The gap is now closed. Section 9.2 prices a ninth
source.

---

## 4. The design question, argued and priced

This is the section the work exists for. `docs/41` section 7.4 named two
candidate answers and priced one of them with nothing synthesised. Six
designs were built and measured here, all with the identical recipe, the
identical source list and the identical baseline, so that the argument
is arithmetic on measurements rather than a preference.

| design | cells | flops | area, um2 | Δ area vs baseline | Δ flops | corrects? |
|---|---:|---:|---:|---:|---:|:---:|
| `HARDEN = 0` — **the baseline** | 1,071 | 163 | **16,714.8576** | — | — | — |
| `mtime` narrowed to 54 bits | 936 | 153 | 15,276.6810 | **−1,438.1766** | −10 | no |
| one parity bit over `mtime` | 1,276 | 164 | 19,244.7738 | **+2,529.9162** | +1 | no |
| residue mod 3 | 1,785 | 165 | 23,649.9480 | **+6,935.0904** | +2 | no |
| **(72,64) SECDED — H6, ships** | **1,599** | **171** | **23,741.6886** | **+7,026.8310** | **+8** | **yes** |
| TMR over `mtime` | 1,923 | 291 | 30,705.8094 | **+13,990.9518** | +128 | yes |
| TMR over `mtime` and `mtimecmp` | 2,610 | 419 | 42,506.9316 | **+25,792.0740** | +256 | yes |

**[fact for every row: `hw/soc/flow/syn_soc.sh soc_clint`, Yosys on
`ihp-sg13g2` at the typical corner, the same `abc` constraint file and
the same 20 ns delay target `hw/soc/out/small-pmp` was synthesised with,
and the same source list in every run. The Δ columns are arithmetic on
two measurements.]**

### 4.1 What a residue check actually detects, and what it misses

A residue-mod-*k* check keeps a shadow register `r` beside the counter,
increments it as `r <= (r + 1) mod k` every tick, and compares it
against `mtime mod k` recomputed from the stored bits.

**Against a single-bit flip it is complete, and the reason is one line
of arithmetic.** A flip at bit *i* changes the value by ±2^*i*. The
check misses it exactly when 2^*i* ≡ 0 (mod *k*). For **any odd
modulus** 2 is invertible mod *k*, so 2^*i* is never 0 mod *k*, and the
residue always moves: **all 64 bits of 64, not most of them.**

**The trap is an even modulus**, and it is worth writing down because it
is the shape a reader reaches for first. Mod 2^*a* the residue is
literally the low *a* bits, and the check is blind to bits *a* through
63: at mod 4 that is **62 of the 64 bits**, and they are the 62 that
matter — a check that covers the harmless end of the counter and none of
the dangerous one. Any modulus with a factor of two loses the top bits
in proportion.

**Against multi-bit errors it is partial, and mod 3 is a good case.**
Modulo 3, 2^*i* ≡ (−1)^*i*, so a two-bit flip at *i* and *j* changes the
residue by ±(−1)^*i* ± (−1)^*j*, which is zero exactly when the two
terms cancel — roughly half of all pairs. A parity bit misses **every**
double error. SECDED misses **none**: that is what the D in SECDED is,
and section 9.3's directed test measures it over 32 disjoint pairs.

### 4.2 Detection is not correction, and a residue cannot be made to
correct cheaply

The residue tells you the clock is wrong. It does not tell you by how
much, so there is nothing to subtract.

Making it correct means making the syndrome *name the bit*: an
arithmetic AN-code in which the 128 values ±2^*i*, *i* = 0…63, are all
distinct mod *k*. That needs *k* > 128, hence **8 check flip-flops — the
same storage as this SECDED** — plus a 128-way syndrome decode that the
Hamming code gets for free from its column structure. So the residue is
not a cheaper corrector. It is only a cheaper *detector*, and section
4.3 is what "cheaper" turns out to mean.

### 4.3 The residue is not cheap, and this is the document's own negative result

> **Measured: the residue-mod-3 detector costs 6,935.0904 um2 and the
> SECDED corrector costs 7,026.8310 um2. The detector is 98.694 % of the
> corrector's price and corrects nothing** **[fact, two synthesised
> designs against one baseline]**.

`docs/41` section 7.4 wrote that a residue check "would *detect* an
upset for a handful of flip-flops". That is true and it is the wrong
measurement. The flip-flops **are** a handful — 2 against 8, and 2
against TMR's 128 — but the flip-flops are not where the area is. The
cost of any check over a 64-bit counter is the **reduction tree that
recomputes the check from the stored bits**, and a mod-3 reduction over
64 bits (32 two-bit chunks, since 4 ≡ 1 mod 3, summed mod 3) is a tree
of 31 mod-3 adders — comparable in silicon to a SECDED encoder and
decoder pair.

**The residue was priced in the wrong currency, and the error is not
small: it is a factor of four in flip-flops and 1.3 % in area.** This is
the same class of mistake `docs/52` measured in the NPU — `evq_data` was
41.2 % of the flip-flops and zero of the rate — and the same correction
applies: count what the thing costs and what it buys, not what it is
made of.

**The genuinely cheap detector is parity**, at **+2,529.9162 um2**, 36.0
% of the corrector. One 64-input XOR tree instead of eight, one
flip-flop instead of eight, and the same 64-of-64 single-bit coverage
the residue gives — with none of its double-error coverage. If
detection alone were the goal, parity is the design and the residue is
strictly dominated by it. Detection alone is not the goal, for section
5's reason.

**So the ordering the measurement gives, and it is not the one `docs/41`
predicted:**

| | Δ area | what it buys |
|---|---:|---|
| parity | +2,529.9162 | detects every single-bit flip |
| residue mod 3 | +6,935.0904 | the same, plus half of double errors |
| **SECDED** | **+7,026.8310** | **corrects every single-bit flip, detects every double** |

**The corrector costs 1.3 % more than the best detector that was
seriously proposed, so the detector is not on the table.** That single
comparison is the whole of the design decision, and it could not have
been made without synthesising both.

### 4.4 Against TMR, and `docs/41`'s estimate made good

`docs/41` section 7.4 wrote:

> `mtime` plus `mtimecmp` is 128 of those flip-flops; tripling them adds
> 256 more. Scaling this document's own measured cost … puts the same
> treatment of the CLINT at roughly **+27,000 um2, about +10 % of the
> Ibex core** **[estimate, a flip-flop-count scaling of one measurement;
> nothing was synthesised]**

**It is now synthesised: +25,792.0740 um2 and exactly +256 flip-flops,
which is +9.356 % of Ibex** **[fact]**. The estimate was **4.68 % high**
and its flip-flop count was exact. That is a good estimate and it is
recorded as one; the point of measuring it is not that it was wrong but
that a decision was declined on a number nobody had produced.

The like-for-like comparison — H6 protects `mtime` alone, so TMR over
`mtime` alone is the right column:

> **The code corrects the same 64 bits for 50.224 % of the area and 6.25
> % of the added flip-flops** **[estimate, arithmetic on two
> measurements]**. Against TMR of the whole 128 bits it is 27.244 % of
> the area and 3.125 % of the flip-flops.

Two things TMR would buy that the code does not, stated because a
cheaper answer that is worse should be argued and not just costed:

- **TMR masks a fault of any multiplicity inside one replica.** Two
  upsets in the same replica in the same cycle are still voted away;
  two upsets in one SECDED word are detected and not corrected. The
  self-scrub in section 3.2 is what makes this second-order — the
  exposure window is one clock — and the campaign cannot measure it,
  because every campaign in this repository is single-bit.
- **TMR needs no combinational cone on the read path.** H6 puts a
  decoder in front of the incrementer, the comparator and the read
  multiplexer. Section 11 states what has and has not been measured
  about that, and the honest answer is that no STA has been run on
  either.

And one thing the code buys that TMR does not, which is `docs/41`
section 4's bound pointed the other way: **the code is one instance of
one proved module, at a width that is fixed by an elaboration guard, so
there is no replication bound to hit, no POL/MIX transform to choose, no
`opt_merge` to defeat and no census that has to prove three banks did
not become one.** Section 9.4 is a shorter guard than `docs/41` section
6 for exactly that reason.

### 4.5 The upper bits are dead, and that is an argument FOR covering them

The alternative nobody had raised: `mtime` is 64 bits and a mission that
lasts years does not need the top half. Checked rather than assumed.

At 20 ns per tick, a mission accumulates 1.578 × 10^15 ticks a year, so:

| mission | ticks | highest bit that can ever be 1 | dead bits |
|---|---:|---:|---:|
| 2 years | 3.156 × 10^15 | 51 | **12** |
| 5 years | 7.889 × 10^15 | 52 | **11** |
| 10 years | 1.578 × 10^16 | 53 | **10** |

**[estimate, arithmetic on the 20 ns SDC period and the Julian year]**

So the premise is true: **11 of the 64 bits are architecturally dead
over a five-year mission.** The conclusion offered with it — that
protecting them is protecting nothing — is false, and it is false in an
instructive way.

**Deadness bounds the fault-free value. It says nothing about the faulty
one.** A bit that is provably zero in a healthy part is still a
flip-flop, and an upset in it sets it. Worse: the dead bits are exactly
the **highest-consequence** bits in the design — bit 63 is a 5,845-year
displacement, bit 54 is 11.4 years — so the dead range is not the part
of the counter that does not matter, it is the part that matters most
and never exercises itself.

**And truncation, priced, buys nothing:**

> **Narrowing `mtime` to 54 bits is measured at −1,438.1766 um2 and −10
> flip-flops** **[fact]**. It reduces the worst single-bit displacement
> from 2^63 ticks (5,845 years) to 2^53 (5.71 years). **Both end the
> mission.** There is no width at which truncation makes the remaining
> bits safe, because the consequence curve is exponential and continuous:
> whatever the top implemented bit is, its upset displaces the clock by
> about the whole mission.

Truncation is also a divergence from the RISC-V privileged
specification's 64-bit `mtime`, in exchange for 0.522 % of the Ibex
core. **It is not a protection; it is a cheaper failure**, and it is
declined.

What deadness *does* buy is a second, independent detector for free: the
top ten bits being provably zero means `|mtime[63:54]` is a fault with
no ambiguity, at about ten gates and no flip-flops. It is ranked and not
built (section 9.3), for two reasons — the code already covers those
bits, and a mission duration hard-coded into a register the architecture
defines as 64 bits is a constant that will outlive the mission it was
chosen for.

---

## 5. Detection is not correction, and what the recovery is

`docs/38-ibex-bringup.md` section 8.5 declined lockstep on exactly this
distinction: **+309,550 um2, +112 % of the core, for *detection* of core
faults and not correction.** The same distinction applies here in
reverse, and it has to be answered rather than assumed, because a
detector with no recovery is a fault channel and should be argued as one.

### 5.1 For the correctable case there is nothing to recover from

This is the case the campaign measures and it is 144 of 144. The
correction happens inside the block, before any port. `mtip` does not
assert early, no bus read returns the corrupt word, and no deadline
moves. Software is *told*, through `BUSSTAT.CNT_MTECC` and its sticky
bit, and what it is told is **telemetry and not an alarm**: this is the
upset-rate counter for the time base, with a scrub period of one cycle,
so every upset in those 72 flip-flops is counted exactly once. Nothing
is required of the handler. It is a number in a frame.

### 5.2 For the uncorrectable case the recovery is a re-epoch, and the
SoC already has the second time base it needs

A double error inside one tick leaves `mtime` wrong and unrepairable.
Two upsets in one 72-bit word inside 20 ns is outside this repository's
fault model, and section 11 says so, but "outside the fault model" is
not "cannot happen" and the recovery has to exist on paper before it is
needed.

**What software can do, in order:**

1. **It is told.** The sticky bit is set and — this is the part that
   makes the report a recovery trigger rather than a log line —
   `BUSSTAT` already drives **fast interrupt line 10, IRQ 22 in the
   frozen map**, gated by `IRQEN`. A handler can be entered on it. The
   interrupt path was built by `docs/44`; this wave adds a source to it
   and nothing else.
2. **It re-epochs.** Every deadline the system holds as an absolute
   `mtime + delta` computed *before* the event is now wrong and must be
   recomputed from the new `mtime`; every deadline computed after it is
   fine. That is a bounded, implementable recovery: re-arm the OS tick,
   re-arm the timeouts, and carry on with a clock whose *rate* is still
   exactly right and whose *origin* has moved.
3. **It re-acquires absolute time.** The correlation between `mtime` and
   UTC is destroyed and has to come from outside — a ground station
   contact, which is what a spacecraft does after any time anomaly.

**And there is a second time base on this die, at zero hardware cost.**
`TICK_DIV = 1` means one `mtime` tick is one system clock, and Ibex's
`mcycle` counts system clocks. Software that records `(mtime0, mcycle0)`
at boot can reconstruct `mtime_true = mtime0 + (mcycle − mcycle0)` after
an uncorrectable event. Three caveats, all of them real and none of them
measured here:

- `mcycle` stops when the core sleeps. The SoC's own bring-up program
  ends in `wfi` — the whole-SoC run reports *"core asleep after 215428
  cycles"* — so a program that sleeps must account for its sleep or the
  reconstruction drifts.
- `mcycle` is itself an unprotected 64-bit counter. It is `docs/42`'s
  `csr_cnt` stratum and it is not covered by `docs/43`'s register-file
  codec. It is a second single point — but an **independent** one, which
  is the property the reconstruction needs.
- `mcountinhibit` can stop it, and nothing in this SoC stops software
  from setting it.

*Partly answered 2026-09-05 by `docs/68-boot-flow.md` section 7.4:*
the epoch's IDENTITY now exists in hardware — a word in the power-on
domain that the boot loader increments once per boot — so a re-epoch is
at least detectable. The reconstruction of elapsed time from `mcycle` is
still [planned].

**This is [planned] and not [fact].** No program in this repository
reconstructs `mtime` from `mcycle`, and this document does not add one:
adding one would change the workload and cost the 215,428-cycle
invariant its meaning as evidence that behaviour did not change. Section
15 item 2 is where it belongs.

### 5.3 So: is the report worth 18 flip-flops?

Stated plainly, because the ratio is bad on its face — the mechanism is
8 flip-flops and its report is 18, which is `docs/56`'s accounting
("twelve are the two reports and not the two mechanisms") in a starker
form.

Yes, and for a reason that is about the mission and not about this
block. `docs/43` section 6.5 wrote that a corrected upset is
*"indistinguishable from no upset at all"* in silicon, and section 10 of
that document called it "the single largest gap this document opens".
The whole of `soc_busstat.v` exists because of that sentence. A
protection added now with no counter behind it would re-open the gap the
previous three waves closed, and the counter is what turns *"the part
survived"* into *"the part survived this often, in this environment"* —
which is the number a radiation-tolerance claim is made of.

The alternative was to spend the bit on the uncorrectable event instead.
It was rejected: under the single-upset fault model the uncorrectable
class is empty, and `docs/44` section 11's rule is that **a mechanism
that ships disabled and has never caught anything is a liability in an
area budget.** A counter that would read zero for the mission is that
mechanism.

---

## 6. Is `mtimecmp` the same problem? No, and it gets nothing

`mtimecmp` is written by software and read by hardware, so it is not
monotonic and the residue trick does not apply to it. But the reason it
is left alone is not that the cheap mechanism does not fit — SECDED
would fit it perfectly, and the campaign could have been run over it.
The reason is `docs/41` section 3.1's criterion, which `mtimecmp` fails
on **both** halves.

**It is not persistent.** Software rewrites `mtimecmp` at every deadline
— that is what a tickless timer driver does — so an upset survives one
interval and not the mission. `mtime` has no such event.

**It is not silent, and the asymmetry is the interesting part.** There
are two directions and both are loud:

- **Corrupted downward**, the deadline is already met, `mtip` asserts at
  once, the handler runs early and rewrites `mtimecmp`. Self-clearing,
  and one spurious interrupt is the cost.
- **Corrupted upward**, the deadline moves out of reach and the timer
  interrupt stops. That is **a missed deadline, which is the exact
  failure the watchdog is the backstop for** — and the watchdog runs on
  the GPTIMER's own prescaler, an independent time base (`docs/40`
  section 4), so nothing the CLINT does wrong can stop it.

**The campaign measures all of this** (section 8.3). Over 128 injections
into `mtimecmp`:

- **the clock was displaced zero times**, worst displacement 0 ticks —
  as it must be, since nothing in `mtimecmp` reaches `mtime`, and the
  measurement is here because "as it must be" is an argument;
- **117 of 128 moved the deadline**, worst move 2,048 cycles;
- **60 of 128 removed the deadline entirely** within the harness's
  4,000-cycle budget — the upward case, and the one the backstop
  catches;
- **57 fired it early** — the downward case;
- **1 was masked.**

> **`mtime`'s upset keeps the interrupts coming and makes them all
> wrong. `mtimecmp`'s upset makes one interrupt wrong or stops it
> altogether, and stopping it is what the SoC already has a backstop
> for.** That is the asymmetry, and it is why the code is over the
> counter and not over the comparand.

The cost of the decision, named: `mtimecmp` is 64 unprotected
flip-flops, an upset in it costs one interval of correct scheduling, and
if it goes the wrong way the recovery is a watchdog reset — which is a
reboot, which is expensive. Section 9.1 ranks it and prices it at
+11,801.1222 um2 (the difference between the two TMR rows in section 4)
should a later wave decide the reboot is too expensive.

---

## 7. Measured area

Same recipe as `docs/39` section 6, `docs/40` section 9 and `docs/41`
section 6.5: `hw/soc/flow/syn_soc.sh`, Yosys `stat -liberty` on
`ihp-sg13g2` typical, `abc` with the same driving cell, the same load
and the same 20 ns delay target. Gate equivalent = `sg13g2_nand2_1` =
7.2576 um2. The Ibex reference is **275,682.6198 um2**
(`hw/soc/out/small-pmp/area.rpt`) **[fact]**.

| Block | Cells | Flops | Area, um2 | kGE | % of Ibex |
|---|---:|---:|---:|---:|---:|
| `soc_clint`, `HARDEN = 0` | 1,071 | 163 | **16,714.8576** | 2.303 | 6.063 % |
| `soc_clint`, `HARDEN = 1` | 1,599 | 171 | **23,741.6886** | 3.271 | 8.612 % |
| `soc_busstat`, seven sources | 713 | 126 | **11,856.6882** | 1.634 | 4.301 % |
| `soc_busstat`, eight sources | 833 | 144 | **13,774.0932** | 1.898 | 4.996 % |
| `soc_clint` as committed at `7721719` | 1,100 | 163 | 16,740.2970 | 2.307 | 6.072 % |

**[fact for every measured row; the percentages are arithmetic on them]**

> **The cost of H6 is +7,026.8310 um2 on the CLINT (+42.04 % of the
> block) and +1,917.4050 um2 on BUSSTAT (+16.17 % of that block):
> +8,944.2360 um2 in total, +26 flip-flops, and +3.244 % of the Ibex
> core** **[estimate, the difference of four measurements]**.

Three readings.

**The baseline must be `HARDEN = 0` and not the committed file, and the
difference is 25.4394 um2 in the direction that would have flattered
this document.** `docs/41` section 6.5 established the rule and the
mechanism here is the same: H6 rewrote the counter's next-state
expression as one continuous assignment shared by both configurations,
and at `HARDEN = 0` that shape is **29 cells and 25.4394 um2 cheaper**
than the committed one, at the identical 163 flip-flops. Quoting the
delta against the committed 16,740.2970 would put H6 at 7,001.3916 um2
— **understating it by 25.4394 um2**, by crediting the hardening with a
saving the refactor made. The direction is small. The habit is not.

**The source list did not move, and that is not luck.**
`hw/soc/flow/syn_soc.sh` already reads `secded_enc.v` and `secded_dec.v`
— they have been in its file list since `docs/43` — so `HARDEN = 0` and
`HARDEN = 1` are measured from **the same files** and differ only by
whether an instance exists. That matters because the script's own header
records that reading three extra files makes `soc_clint` 29.3328 um2 and
5 cells *bigger*, and `docs/45` section 4.3 measured it: a per-block
area from this script reproduces against the file list as it stood on
the day. Here the list is identical across every row of section 4's
table and every row of this one.

**Where the area goes.** 528 cells and 8 flip-flops. The eight
flip-flops are the check field; the 528 cells are two XOR-tree cones —
`secded_enc.v`'s eight rows of weight 26, and `secded_dec.v`'s eight
again plus the 64-column syndrome match and the correction XOR — and the
widening of the incrementer's and comparator's input cones that follows
from feeding them the decoder's output instead of a register. **No
attempt was made to reduce it**, and section 15 item 4 says what would.

---

## 8. The campaign, and its calibration

`hw/soc/tb/cocotb/test_soc_clint_fi.py`, a new suite on the model of
`test_soc_wdog_fi.py`: the DUT is `soc_clint` itself, only the stimulus
reaches into the hierarchy, and every observation is one a bench could
make — the two interrupt pins, the fault pin, and what a bus master
reads back.

### 8.1 The workload, and why `mtime` is seeded

Out of reset `mtime` is zero and stays under 2^10 for the length of any
simulation anyone will run. **A campaign drawn there would flip bit 47
of a register whose bit 47 is zero, in a design where every deadline is
also small, and would conclude that the high half of the counter does
not matter.** It matters for exactly the reason section 2 gives.

So the bring-up — outside the injection window — writes `mtime` to
`0x0003_5A6C_39F1_84B2` through the architectural two-store sequence
this block implements, arms a deadline 200 ticks ahead through the
architectural three-store sequence, and only then opens the window. The
seed has **25 bits set out of 64** **[fact]**, spread across the whole
word, so a drawn flip is about as likely to clear a one as to set a
zero. Control 4 asserts that the high half really is the seeded one on
the clean run and control 3 that the clock advances one per clock.

The clean run is **224 cycles with a 212-cycle injection window**
**[fact]**, identical in both builds.

### 8.2 The oracle for the clock is arithmetic, and the first one was wrong

This is worth a subsection because the first version produced a
confident wrong number, and it is the shape `docs/16` section 1.8
exists to catch.

The obvious oracle is a diff: compare each read of `mtime` against the
golden read with the same label. It is wrong, and the campaign
demonstrated it. **An upset in `mtimecmp` changes how long the run
takes**, so the final read-back happens on a different cycle, so `mtime`
legitimately reads differently — and the harness reported **115 of 128
`mtimecmp` injections as having corrupted the clock**. They had not.
`mtimecmp` cannot reach `mtime`; the workload had moved underneath the
measurement.

What `mtime` actually promises is C1 of `soc_clint_props.v`: at
`TICK_DIV = 1` it advances **exactly one per clock**. So `mtime − cycle`
is a constant for the whole run, the golden run measures that constant,
and every read in every injected run is checked against it. Control 3
asserts the constant is a constant. The check is then independent of how
long the run took, which is what makes it a check on the clock rather
than on the schedule.

An earlier version had a second defect of the same family and it is
recorded in the harness: the observer coroutine's stop condition was in
the loop *condition* rather than after the sample, so it completed one
more body after the run ended — during the next run's power-on reset,
where `mtimecmp` and `mtime` are both zero and `mtip` is therefore high.
It appended that transition to the **finished** run's trace. Three
symptoms, one race: a clean run did not reproduce itself, no injection
ever classified MASKED, and every record read "the deadline moved" while
reporting that it had moved by zero cycles.

### 8.3 The two campaigns

342 injections hardened and 326 unhardened — every bit of every target,
twice, at seeded-random cycles inside the measured window. The seed is
derived **per target bit** rather than consumed from one stream, so the
cycle drawn for `mtimecmp` bit 3 is the same number in both builds
whatever else is in the target list. That is what makes section 8.4's
calibration possible.

**Hardened — the design that ships:**

| stratum | bits | n | MASKED | CORRECTED | SDC | HANG | clock displaced | announced |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mtime` | 64 | 128 | 0 | **128** | 0 | 0 | **0** | **128** |
| `mtime_chk` | 8 | 16 | 0 | **16** | 0 | 0 | **0** | **16** |
| `mtimecmp` | 64 | 128 | 1 | 0 | 67 | 60 | **0** | 0 |
| `msip` | 1 | 2 | 0 | 0 | 2 | 0 | **0** | 0 |
| `rdata_o` | 32 | 64 | 62 | 0 | 2 | 0 | **0** | 0 |
| `rvalid_o` | 1 | 2 | 2 | 0 | 0 | 0 | **0** | 0 |
| `err_o` | 1 | 2 | 2 | 0 | 0 | 0 | **0** | 0 |
| **total** | **171** | **342** | **67** | **144** | **71** | **60** | **0** | **144** |

**[fact, `hw/soc/tb/cocotb/records_soc_clint_fi.csv`]**

**Unhardened — the design `docs/40` shipped, same draws:**

| stratum | bits | n | MASKED | SDC | HANG | clock displaced | worst displacement | announced |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `mtime` | 64 | 128 | 0 | 84 | 44 | **95** | **9,223,372,036,854,775,808 ticks** | **0** |
| `mtimecmp` | 64 | 128 | 1 | 67 | 60 | 0 | 0 | 0 |
| `msip` | 1 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| `rdata_o` | 32 | 64 | 62 | 2 | 0 | 0 | 0 | 0 |
| `rvalid_o`, `err_o` | 2 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| **total** | **163** | **326** | **67** | **155** | **104** | **95** | **2^63** | **0** |

**[fact, `records_soc_clint_fi_h0.csv`]**

**Five readings.**

**The mechanism does what it claims, on every bit.** 128 of 128 draws
into `mtime` and 16 of 16 into the check field come back CORRECTED, with
the clock on the value the arithmetic predicts, the deadline on its
golden cycle, and `mt_ecc_o` high for exactly one cycle. Not a sample of
the bits: every one of the 64, twice.

**2^63 is the number the three deferrals were about.** In the
unprotected design the worst single injection displaced the clock by
9,223,372,036,854,775,808 ticks — **5,845 years at 20 ns** — and
**nothing on the part said so**. That is `docs/40` section 10 item 2's
"silently wrong clock", measured.

**95 of 128 and not 128 of 128, and the 33 are worth naming.** An upset
displaces the clock only if the flipped bit is one the read sequence
subsequently observes and the run reaches its final read-back. 44 of the
128 hung — a flip in a high bit *downward* takes `mtime` below the
deadline for ever, so `mtip` never rises and the harness's bounded wait
expires — and a run that never read the clock back is not evidence that
the clock was right. The campaign keeps **displaced** and **not
observed** in separate columns for that reason, and the summary line
reports both.

**The new state is measured and not exempted.** `mtime_chk` is eight
flip-flops H6 *added*, and an upset can land in them exactly as it can
land in the data. They are a stratum of their own — `docs/43`'s
`regfile_ecc` argument — so that folding them into `mtime` cannot move
that stratum's rate for two unrelated reasons at once. 16 of 16 come
back CORRECTED: a flip in a check bit produces a syndrome that names a
check bit, the data is untouched, and the re-encode repairs the field.

**Nothing outside the codeword is announced.** `mt_ecc_o` fired on 144
of 342 injections and all 144 are inside the 72 protected bits. That is
an acceptance criterion and not an observation: a fault line that fired
on an upset in `rdata_o` would make `BUSSTAT.CNT_MTECC` a counter of
something else's upsets, which is the aggregation `soc_busstat.v`'s
header is built to avoid.

### 8.4 The calibration, and the drift is exactly zero

`docs/55` section 8.3 had to refuse a 19 % improvement because its
frozen-die stratum moved on 15 of 100 records; `docs/56` reported its
delta because the same calibration came back at zero. This wave changes
**no software at all** — H6 and the BUSSTAT source are RTL — so the two
builds run the same program over the same draws, and the strata H6 does
not touch have to come back identical or the delta is a difference of
two things.

| | hardened | unhardened |
|---|---:|---:|
| clean run | 224 cycles | **224** |
| measured injection window | 212 cycles | **212** |
| records in untouched strata | 198 | 198 |
| **records that changed verdict** | — | **0 of 198** |
| drawn cycles identical | — | **198 of 198** |

**[fact, a field-by-field diff of the two `records_*.csv` files over
`mtimecmp`, `msip`, `rdata_o`, `rvalid_o` and `err_o`]**

> **NOT ONE OF THE 198 RECORDS IN THE STRATA H6 DOES NOT TOUCH CHANGED
> ANYTHING — not its class, not its `clock_ok`, not its displacement,
> not its drawn cycle.** So the 128-of-128 in `mtime` is a property of
> the mechanism and not of two campaigns that happened to be run.

### 8.5 The whole-SoC invariant

`docs/56` measured it once because it changed only RTL. So does this.

| build | cycles |
|---|---:|
| `docs/55` and `docs/56`, the design of record | 215,428 |
| **H6 + the eighth BUSSTAT source** | **215,428** |

**[fact, `hw/soc/flow/sim_soc.sh`, 27 of 27 checks passing with a zero
fail mask, and the console decoding 760 characters with 0 framing
errors]**

> **THE CORRECTION COSTS ZERO CYCLES**, reproducing the invariant to the
> cycle. It must: in a fault-free machine the decoder is the identity,
> which is E2 of `soc_clint_props.v` proved by induction and not
> assumed.

**Every document after this one should go on quoting 215,428.**

### 8.6 What running it cost

342 injections plus controls, and 326 plus controls for the
counterfactual, each as ONE Icarus process rather than one process per
injection — which is why the whole campaign is a matter of seconds where
`docs/56`'s took an hour.

**And the runtime is not quotable as a figure.** Four runs of the
identical hardened campaign on the same host, in the order they were
made, took **140.2 s, 218.0 s, 38.2 s and 20.8 s** **[fact, the cocotb
`REAL TIME` column]**; the unhardened one took **74.0 s**. The
difference is host load: three syntheses, a formal job and a whole-SoC
simulation were running for part of the first two. `docs/44` section
9.5's rule is to quote the cost with the configuration it was measured
in, and the honest form of that here is that **this campaign's runtime
varies by a factor of ten with what else is on the machine**, so it is
quoted as a range and not as a figure of merit. What is stable across
all five runs is the result: the same 342 records with the same
verdicts.

The expensive part of this wave is not the campaign. It is section 9.3.

---

## 9. What was deliberately not built, ranked and priced

### 9.1 Inside this block

| what | bits | why not | price if it were |
|---|---:|---|---:|
| `mtimecmp` | 64 | Section 6: not persistent — software rewrites it every interval — and not silent, because its worst direction is a missed deadline and the watchdog is the backstop for missed deadlines | **+11,801.1222 um2**, the difference between section 4's two TMR rows, or about +7,000 for a second SECDED word **[estimate]** |
| `msip` | 1 | One bit cannot be tripled — `docs/30` section 3.3's bound, and `docs/33` section 5 proves the one-bit case cannot be rescued by polarity — and there is nothing in this module to bundle it with that shares its write policy. Software sets and clears it, and it reads back | a bundle that does not exist |
| `rdata_o`, `rvalid_o`, `err_o` | 34 | `docs/41` section 3.1's "a register the block itself overwrites every tick sheds an upset on its own". **Measured**: 66 of 68 injections MASKED, 2 SDC, none reaching the clock | not estimated |
| the dead-bit check, `\|mtime[63:54]` | 0 | Section 4.5. The code already covers those bits, and a mission duration hard-coded into an architecturally 64-bit register is a constant that outlives its reason | about ten gates |

### 9.2 A ninth BUSSTAT source, which would separate the two classes

`CNT_MTECC` **conflates a correction with an uncorrectable**, which is
the exact aggregation `soc_busstat.v`'s own header criticises
`pilot_top.v` for making. It is done knowingly and here is the whole of
the reason:

- **There is one bit left.** STATUS puts `irq_o` at bit 8 and the file
  forbids moving it, because that bit is in `hw/soc/tb/sw/soc_timers.h`
  and in every program written against the block. The sticky field grew
  into bit 7 and the gap is closed. A ninth source either moves the
  interrupt bit or puts the sticky field on both sides of it.
- **The class it hides is empty under the fault model.** An uncorrectable
  needs two upsets in one 72-bit word inside one 20 ns tick, because the
  codeword is re-encoded every clock. Every campaign in this repository
  is single-bit.
- **It would cost 18 flip-flops** — 16 of counter, one sticky, one
  enable — **for a counter that reads zero for the mission**, which is
  `docs/44` section 11's named liability.

**The cost is stated rather than glossed: an operator watching
`CNT_MTECC` move cannot tell a healed clock from a wrong one.** What
can tell them apart is section 5.2's comparison against `mcycle`, in
software, and that is the item section 15 ranks first.

### 9.3 The proof got expensive, and that is a cost of this design

| task | before H6 | after H6 |
|---|---:|---:|
| `soc_clint` bmc, depth 20 | **6 s** | **18 min 19 s** |
| `soc_clint` prove, k-induction | **2 s** | **5 min 57 s** |
| `soc_clint` cover | ~0 s | ~0 s |

**[fact, SymbiYosys `Elapsed clock time`, yices, the same host; the
"before" column is the committed `soc_clint.v` and its committed
property file, run in a scratch directory]**

**A factor of 183 on the bounded check and 179 on the proof**, and it is
a property of the design and not of a mistake: E1 asserts that eight XOR
reductions of weight 26 over a 64-bit counter equal eight stored bits,
in every reachable state, and that is a hard problem for an SMT solver
in a way that a 22-bit voted word is not.

It is affordable — twenty-four minutes, once — and it is recorded
because it is the kind of number that decides whether the same technique
is applied to the next 64-bit register. `formal/secded.sby` proves the
codec on its own in seconds; what costs is proving the *invariant over a
counter*.

### 9.4 The census is shorter than `docs/41`'s, and says so

`docs/41` section 6 is four pages because TMR is **deliberately
redundant logic and a synthesiser is built to delete it**. H6 is not
redundant: the check bits feed a decoder whose output feeds real
flip-flops, so no structural pass can merge them away, and the guard is
correspondingly shorter.

`sw/tests/test_soc_synthesis_guards.py` section 8 measures, with the
recipe `syn_soc.sh` runs **[fact]**:

| | mapped flip-flops |
|---|---:|
| `HARDEN = 1` | **171** |
| `HARDEN = 0` | **163** |
| the detect-only mutation | **171** |

and asserts that `u_mtime_enc` and `u_mtime_dec` both still have cells
under them in the mapped netlist after the post-mapping flatten. The
encoder is the half a reader would expect to disappear — its output goes
to eight flip-flops whose only consumer is the decoder, and a pass that
could prove the sequential invariant `chk == encode(mtime)` would be
entitled to delete the pair. Nothing in this flow proves sequential
invariants, so nothing does; that is a property of the tool and the
census is the measurement that says it held.

**The third row is the point, and it is asserted rather than
discovered.** `test_the_census_cannot_tell_a_corrector_from_a_detector`
builds the mutation that ticks from the stored value instead of the
corrected one — H6 turned into the detect-only design section 4 rejects
— and **asserts that the flip-flop count does not change**. `docs/43`
section 9.4 found twenty formal tasks green on a design whose three
banks had collapsed into one, and concluded that formal cannot see what
only the census can; this is the mirror of that sentence, in the
census's own file. The check that fails on that mutation is the
campaign, where 128 CORRECTED become 0.

The wrong-way-round edits are therefore guarded **textually**, by
`test_the_clint_corrects_on_every_path_that_reads_the_counter`, which
asserts that the encoder covers `mtime_next`, that the decoder reads the
stored codeword, and that `mtime_q` — the raw, possibly corrupt register
— is read **nowhere except** the decoder and its own next-state
assignment. Every other consumer reads the corrected wire, and the test
fails on any line that does not.

---

## 10. Verification

Four kinds of evidence, and `docs/41` section 6's division between them:
each is blind to what the others see.

### 10.1 The regression

| suite | before | after |
|---|---:|---:|
| `.venv/bin/python -m pytest sw/tests -q` | 382 **[estimate, 388 less this wave's six]** | **388 passed** **[fact]** |
| `hw/soc/tb/cocotb`, `Makefile.soc_clint` | 12 | **17 passed** |
| `hw/soc/tb/cocotb`, `Makefile.soc_busstat` | 10 | **10 passed** |
| `hw/soc/tb/cocotb`, `Makefile.soc_clint_fi` | — | **3 passed** (new) |
| `hw/soc/formal`, `make clint` | 3 tasks | **3 tasks, all pass** |
| `hw/soc/formal`, `make busstat` | 4 tasks | **4 tasks, all pass** |
| `hw/soc/flow/sim_soc.sh` | 27 checks | **27 checks, fail mask 0** |

**[fact]**

**A CONCURRENT WAVE IS IN THE SAME WORKING TREE and the counts above are
this wave's, measured when its tests were added.** A re-run at the end
of the session collects **395** and reports **one failure**, and neither
number is this document's: the seven extra tests and the one failure —
`docs/57-power-under-a-duty-cycle.md` not yet named in
`docs/00-index.md` — belong to the activity-annotated power work being
done alongside it. Reviewing the two together is what will reconcile
them. Nothing this document touches fails in that run.

One thing that is *not* a regression and is recorded so that a reader
does not chase it: `make -f Makefile.soc_clint` ends in a **segmentation
fault during Icarus/cocotb teardown, after all tests have passed and the
results file has been written**. It is not caused by this work — the
committed `soc_clint.v` run through the identical recipe segfaults the
same way on this host — and it deletes `results_soc_clint.xml`, so the
suite's own artifact is absent while its console output says
`TESTS=17 PASS=17 FAIL=0`.

### 10.2 Five new directed cocotb tests

They are directed and not a campaign, because a rate cannot express an
individual claim and because one of them reaches a class the campaign
cannot:

- `test_the_stored_word_is_always_a_codeword` — E1 as a measurement.
  The check bits are recomputed in Python from the eight H rows, written
  out again rather than read off the instance, and compared on every
  cycle of a run that ticks, that is written whole-word and that is
  written with byte lanes.
- `test_a_single_upset_in_mtime_never_reaches_a_port` — **all 64 data
  bits**, not a sample, because the argument is about the high ones.
- `test_a_single_upset_in_the_check_bits_is_corrected_too` — all 8.
- `test_a_double_upset_is_detected_and_never_miscorrected` — **the class
  the campaign cannot reach.** Over 32 disjoint pairs, the data field is
  passed through untouched, the event is announced exactly once, and the
  counter continues from the corrupt value **and from no other**. A
  miscorrection would appear as a third value. This is what the odd
  column weights buy and it is the reason for SECDED rather than a plain
  Hamming code.
- `test_nothing_is_reported_when_nothing_is_wrong` — 150 randomised
  accesses of every shape the block has, plus an unmapped offset, with
  `mt_ecc_o` asserted low throughout. A fault line that pulses on
  healthy traffic turns the mission's upset-rate telemetry into noise.

All five skip cleanly at `HARDEN = 0`, so the suite runs against either
configuration.

The deposit phase in these tests is `T_INJECT = 4` ns into a 10 ns
cycle, after the stimulus is driven and before the sampling point, and
that is load-bearing: the first version deposited 1 ns before the clock
edge that immediately re-encodes the word, so the correction happened,
the pin pulsed between two sampling points, and three tests reported
that a corrected upset had been corrected *silently*. It had not.
Nothing was looking when it was announced.

### 10.3 Formal

`hw/soc/formal/soc_clint.sby` gains two clauses and keeps the other
seven **byte for byte**, which is itself the claim H6 makes about
transparency:

- **E1**: `mtime_chk_q == encode(mtime_q)` in every reachable state.
  That is the self-scrub stated as an invariant, and it is what makes
  the induction close — without it, k-induction starts from a state
  whose check bits are arbitrary and every clause below fails there for
  a reason that says nothing about the design.
- **E2**: `mtime == mtime_q`, so the decoder is the identity and the
  codec is invisible to C1, C3 and the ghost architectural state. Plus
  **E2b**: `mt_ecc_o` is low in a fault-free machine.

The H matrix is written out again in the property file rather than read
off the encoder instance, for `secded_enc.v`'s own stated reason: a
check that read the design's output would be comparing the design
against itself.

**What is NOT proved here, and it is the important half.** Nothing in
the harness injects a fault, because a formal harness that deposits into
a register is proving a property of the harness. E1 and E2 are
statements about the fault-free machine; **the correction is measured
and never proved**, in section 8 and in section 10.2. The codec itself
is proved once, for every consumer, in `formal/secded.sby`.

The two codec files are added to the job's `[files]` and read alongside
`soc_clint.v`; `SOC_CLINT_HARDENED` guards E1 and E2 so the property
file still elaborates at `HARDEN = 0`, where `mtime_chk_q` does not
exist.

### 10.4 The netlist census

Section 9.4.

---

## 11. What this does NOT cover

Stated at length, because a green check is only as wide as what it
examined and this repository has been bitten by that shape nine times
now — `docs/28` 4.4a, `docs/34` 8.5, `docs/36` 3.3, `docs/38` 7.3 and
8.2, `docs/39` 3, twice in `docs/40`, and `docs/56` section 5.1's stall
that no injection reached.

- **The campaign is RTL, single-bit, flip-flop only.** No gate-level
  netlist, no back-annotated timing, no multi-bit strike.
- **AND SINGLE-BIT IS A LARGER GAP FOR THIS MECHANISM THAN FOR A TMR
  BLOCK.** H6's defence is a combinational encoder and a combinational
  decoder in the datapath, and **a single-event transient inside either
  one is a fault model this harness cannot express**. A TMR bank's
  defence is storage, and `docs/41` section 7.5 makes the same
  disclaimer about its voter; here the exposed combinational area is
  528 cells rather than a 22-bit majority gate. This is the most
  significant thing this document does not measure.
- **The uncorrectable class is empty by construction and therefore
  unmeasured in the campaign.** `test_a_double_upset_is_detected_and_never_miscorrected`
  drives 32 of them directly, which is a directed test and not a rate.
- **No STA has been run on this block, before or after.** The decoder is
  now in front of a 64-bit incrementer and a 64-bit comparator, and the
  only timing statement anywhere in this document is that `abc` was
  given a 20 ns target and did not report failing it. **That is not a
  timing sign-off and it is not evidence of one.** `docs/44` sections
  5.1 to 5.3 are three corrections to how this repository reads its own
  timing numbers, and none of them has been applied here.
- **No place-and-route.** No block under `hw/soc/` has been through it
  except by way of `docs/47`'s `soc_top` run, which predates all of
  this.
- **`soc_top` has not been re-synthesised as one design.** `docs/45`
  made that possible and `syn_soc_top.sh` still exists; the numbers in
  section 7 are per-block and inherit `docs/45` section 4.3's
  file-list caveat.
- **The report is a counter, and DETECTED depends on someone looking.**
  `BUSSTAT.CNT_MTECC` saturates, is software-clearable, and the software
  that would read it may be the thing that failed.
- **`CNT_MTECC` cannot distinguish a correction from an
  uncorrectable.** Section 9.2.
- **Nothing here measures the CLINT inside the SoC with a core in front
  of it.** The whole-SoC run in section 8.5 is a functional check, not
  an injection campaign; `hw/soc/fi/targets.py` covers the core and
  `npu_targets.py` the NPU connection, and **neither covers any
  peripheral.** There is still no whole-SoC fault-injection campaign
  that can reach `soc_clint`.
- **The recovery in section 5.2 is [planned].** No program reconstructs
  `mtime` from `mcycle`, and the three caveats on doing so are stated
  and not measured.
- **One workload, one seed, one parameter point.** `TICK_DIV = 1`, one
  seed, 2 draws per bit. `docs/16` section 7.5's disclaimer applies
  unchanged: every number here is conditional on an upset having landed
  in the window.

---

## 12. Corrections to earlier documents

**`docs/41` section 7.4's estimate is superseded by a measurement, and
it was good.** "+27,000 um2 ... 256 more flip-flops" is measured at
**+25,792.0740 um2 and exactly +256 flip-flops**. Section 4.4.

**`docs/41` section 7.4's suggestion that a residue check is the cheap
answer is refuted.** "a residue or parity check over it would *detect*
an upset for a handful of flip-flops" is true about flip-flops and false
about cost: the residue is **98.694 %** of the corrector's area. Section
4.3. The sentence is not withdrawn — it pointed at the right structural
property, which is that a monotone counter is checkable without a copy
of itself — but the conclusion drawn from it, that detection is what one
can afford, does not survive being synthesised.

**`docs/60-soc-datasheet.md` v0.1 is pinned to commit `7721719` and is
correct there.** Six of its statements are superseded by this work and
are listed here rather than edited, because a datasheet that says which
commit it describes should not be silently retargeted at another one:

- section 5.4, "**`mtime` and `mtimecmp` are unprotected**, 128
  flip-flops of them" — half of that is now false;
- section 5.4's CLINT area row, 1,043 cells / 163 flops / 16,712.8164
  um2, which is `docs/45` section 6.2's number under a third file list;
  this document's baseline is 1,071 / 163 / 16,714.8576 and its shipped
  figure is 1,599 / 171 / 23,741.6886;
- section 5.4's "+27,000 um2" estimate, superseded above;
- section 5.7 and section 1's "**four** saturating counters and four
  sticky status bits", which was already stale at `docs/55` (seven) and
  is now eight;
- section 9.1's protection table, which needs a row for the time base;
- section 9.8's "**`mtime` and `mtimecmp`**, 128 flip-flops, ranked
  first for the next hardening wave since `docs/44` and still
  unaddressed";
- section 15's "33 SymbiYosys tasks collected", which this work moves.

A v0.2 revision row is section 15 item 5.

**Nothing in `docs/55` or `docs/56` moves.** The 215,428-cycle invariant
is reproduced exactly and no NPU number is touched.

---

## 13. Files touched

### 13.1 RTL

| file | change |
|---|---|
| `hw/soc/rtl/soc_clint.v` | H6. A `HARDEN` parameter defaulting to 1; `mtime` renamed to `mtime_q` with `mtime` becoming the corrected wire; `mtime_chk_q`; instances of `secded_enc` and `secded_dec`; the `mt_ecc_o` port; a header section arguing the whole of section 4 in the file a reader of the block will open |
| `hw/soc/rtl/soc_busstat.v` | The eighth and last source, `S_MTECC` at bit 7, with `REG_MTECC` at `0x028` and the STATUS gap closed |
| `hw/soc/rtl/soc_top.v` | `clint_mt_ecc_ev`, from `u_clint` to `u_busstat` |

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified. `docs/34`'s freeze is untouched.**

### 13.2 Harness, tests and headers

| file | change |
|---|---|
| `hw/soc/formal/soc_clint_props.v` | E1, E2, E2b, and the H matrix written out again |
| `hw/soc/formal/soc_clint.sby` | reads the two codec files; defines `SOC_CLINT_HARDENED` |
| `hw/soc/tb/cocotb/test_soc_clint_fi.py` | **new**, the campaign |
| `hw/soc/tb/cocotb/Makefile.soc_clint_fi` | **new**, and the unhardened counterfactual invocation in its header |
| `hw/soc/tb/cocotb/test_soc_clint.py` | five directed H6 tests and the deposit helper |
| `hw/soc/tb/cocotb/Makefile.soc_clint` | reads the two codec files in **both** configurations, so a source list cannot move with a parameter |
| `hw/soc/tb/cocotb/test_soc_busstat.py` | the eighth source, and `NSRC` 7 → 8 |
| `hw/soc/tb/sw/soc_timers.h` | `BST_MTECC`, `BST_S_MTECC`, and the units read off the name |
| `sw/tests/test_soc_synthesis_guards.py` | section 8: six guards, of which one asserts that the census **cannot** see something |

`records_soc_clint_fi.csv` and `records_soc_clint_fi_h0.csv` are the
campaign's per-record output and are what section 8.4's calibration
diffs.

---

## 14. Reproducing this

```
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests -q

hw/soc/flow/sim_soc.sh                       # 27 checks, 215,428 cycles

cd hw/soc/tb/cocotb && make -f Makefile.soc_clint
cd hw/soc/tb/cocotb && make -f Makefile.soc_busstat
cd hw/soc/formal && make clint                # ~24 minutes, section 9.3
cd hw/soc/formal && make busstat
```

The two campaigns, and the second is the calibration:

```
cd hw/soc/tb/cocotb
make -f Makefile.soc_clint_fi
make -f Makefile.soc_clint_fi \
     EXTRA_COMPILE_ARGS=-Psoc_clint.HARDEN=0 \
     SOC_CLINT_FI_UNHARDENED=1 \
     SIM_BUILD=sim_build_soc_clint_fi_h0 \
     COCOTB_RESULTS_FILE=results_soc_clint_fi_h0.xml
```

then the record-for-record diff over the strata H6 does not touch —
which is the check, and running it is the only thing that produces
section 8.4's zero:

```
python3 - <<'EOF'
import csv
load = lambda p: {(r["stratum"], r["bit"], r["cycle"]): r
                  for r in csv.DictReader(open(p))
                  if r["stratum"] not in ("mtime", "mtime_chk")}
a, b = load("records_soc_clint_fi.csv"), load("records_soc_clint_fi_h0.csv")
assert set(a) == set(b), "the draws are not the same draws"
print(len(a), "records,", sum(a[k] != b[k] for k in a), "changed verdict")
EOF
```

The area table, every row with the same recipe and the same source list:

```
hw/soc/flow/syn_soc.sh soc_clint                     hw/soc/out/h58-h
SOC_CHPARAM="-set HARDEN 0" \
  hw/soc/flow/syn_soc.sh soc_clint                   hw/soc/out/h58-h0
hw/soc/flow/syn_soc.sh soc_busstat                   hw/soc/out/h58-bst
#   ... and `git stash` for the seven-source BUSSTAT row.
```

The four alternative designs in section 4 are **mutations of
`hw/soc/rtl/soc_clint.v` measured and then reverted**, the shape
`docs/56` section 14 records for its own baseline rows: each writes a
scratch variant into the file, runs `syn_soc.sh soc_clint`, and restores
the working copy in a `finally` block. The variants are TMR over
`mtime`, TMR over `mtime` and `mtimecmp`, `mtime` narrowed to 54 bits, a
residue-mod-3 detector and a parity detector; each is the H6 generate
block replaced by the alternative, with the rest of the file untouched
so that the source list and every other structure are held constant.
**None of them is committed and none of them is in the tree**, which is
the same status `docs/41` section 6.3's mutations have.

The proof-cost comparison in section 9.3 uses the committed
`soc_clint.v` and its committed property file, copied into a scratch
directory with a two-task `.sby`, so that the "before" column is the
design and not a reconstruction of it.

---

## 15. What the next block should be

1. **Software that reconstructs `mtime` from `mcycle`, and a test that
   proves the two advance together.** Section 5.2 is the recovery this
   wave's detection enables and it is entirely on paper. The measurement
   is cheap — `mtime − mcycle` is a constant for the whole 215,428-cycle
   run or it is not — and it would turn the one thing `CNT_MTECC`
   cannot tell an operator into something software can. It changes the
   workload, so it costs the invariant its meaning as evidence and has
   to be done in a wave that says so.
2. **A whole-SoC fault-injection campaign that can reach a peripheral.**
   `hw/soc/fi/targets.py` covers the core and `npu_targets.py` the NPU
   connection; **nothing covers the CLINT, the GPTIMER, the watchdog,
   the UART, the fabric or the memories inside a running SoC.** Every
   campaign in this repository that touches those blocks is
   block-level, with a synthetic workload and a hand-written oracle.
   The one in this document is the fourth of them and the argument for
   a fifth is getting thinner than the argument for the first whole-SoC
   one.
3. **The memory contents.** `soc_mem.v` stores no check bits, the SCRUB
   slot is a reserved address, and **72 KiB of RAM and ROM is the
   largest storage in the design with nothing checking a word read out
   of it**. After this wave it is also the largest unprotected thing
   left, by two orders of magnitude over anything in section 9.1. The
   codec this document instantiates is (72,64) and the RAM macro is 64
   bits wide.
   *Corrected 2026-09-05:* done in `docs/67-memory-protection.md`, and
   the width coincidence was not the answer: (72,64) needs eight bits
   the row does not have, and what fits is four (16,8) shortenings of
   the same code.
4. **Timing, for the first time on this block.** Section 11's fourth
   bullet. A decoder in front of a 64-bit incrementer is exactly the
   shape `docs/43` put in front of the register file's read port and
   `docs/44` then spent three sections learning to measure. Doing it
   here is a day and it would say whether section 7's area is the whole
   price.
5. **A v0.2 of `docs/60`.** Section 12 lists seven statements in the
   datasheet that this wave supersedes, and a datasheet whose corrections
   live in another document is a datasheet nobody will read the
   corrections of.
