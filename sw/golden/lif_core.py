"""Bit-exact golden model of the time-multiplexed LIF neuron core.

This file is the executable form of the numbered equations in
docs/10-npu-mvp-spec.md section 4 (E1..E8) and 11.2 (E10). The RTL is
verified against it bit-for-bit. It deliberately uses plain Python ints,
not numpy: no hidden dtype promotion, no float contamination — every
operation is the integer operation the hardware performs.

Per synaptic event with axon id a, for each neuron j in ascending order
(refractory neurons gated per E7):

    w  = sext4(W[a][j])                       (E1)  w in [-8, +7]
    c  = w * 2**S_SYN                         (E2)  exact, no truncation
    V' = sat16(V + c)                         (E3)  clamp to [-32768, 32767]
    spike iff V' >= THETA                     (E4)  after the update
    on spike: V = V_RESET, R = T_REFR         (E5)

Per TICK event, for each neuron j in ascending order:

    leak toward zero by max(|V| >> S_LEAK, 1) (E6)  sign never flips
    R = R - 1 if R > 0                        (E7)

Ordering and determinism are normative (E8): FIFO event order, ascending
neuron scan, spikes emitted in scan order.
"""

V_BITS = 16
V_MAX = (1 << (V_BITS - 1)) - 1  # +32767
V_MIN = -(1 << (V_BITS - 1))  # -32768
W_MIN = -8  # 4-bit signed two's complement (E1)
W_MAX = 7
R_MAX = 15  # 4-bit refractory counter
WEIGHTS_PER_WORD = 16  # 64-bit weight SRAM data word (spec section 5)

SYN_SHIFT_MAX = 7
LEAK_SHIFT_MAX = 15


def _check_int(name, value):
    """Reject anything that is not a plain int (floats, bools, numpy)."""
    if type(value) is not int:
        raise TypeError(f"{name} must be a plain int, got {type(value).__name__}")
    return value


def sat16(x: int) -> int:
    """Saturate to the signed 16-bit membrane range (E3)."""
    if x > V_MAX:
        return V_MAX
    if x < V_MIN:
        return V_MIN
    return x


def leak_value(v: int, shift: int) -> int:
    """One leak step: shift-based decay toward zero, minimum step 1 (E6).

    |v| is evaluated exactly (the hardware magnitude path is 16-bit
    unsigned; |-32768| = 32768 is representable). The sign never flips
    and |result| < |v| for any nonzero v.
    """
    if v == 0:
        return 0
    mag = v if v > 0 else -v
    m = mag >> shift
    if m == 0:
        m = 1
    return v - m if v > 0 else v + m


class LIFConfig:
    """Core-global configuration for one pass (spec section 6).

    Validation mirrors the RTL ERR_CFG conditions: the golden model raises
    where the hardware refuses to start.
    """

    def __init__(self, thresh, v_reset=0, leak_shift=3, syn_shift=0,
                 refr_period=0, leak_en=True):
        _check_int("thresh", thresh)
        _check_int("v_reset", v_reset)
        _check_int("leak_shift", leak_shift)
        _check_int("syn_shift", syn_shift)
        _check_int("refr_period", refr_period)
        if not 1 <= thresh <= V_MAX:
            raise ValueError(f"thresh {thresh} outside [1, {V_MAX}]")
        if not V_MIN <= v_reset < thresh:
            raise ValueError(f"v_reset {v_reset} outside [{V_MIN}, thresh-1]")
        if not 0 <= leak_shift <= LEAK_SHIFT_MAX:
            raise ValueError(f"leak_shift {leak_shift} outside [0, {LEAK_SHIFT_MAX}]")
        if not 0 <= syn_shift <= SYN_SHIFT_MAX:
            raise ValueError(f"syn_shift {syn_shift} outside [0, {SYN_SHIFT_MAX}]")
        if not 0 <= refr_period <= R_MAX:
            raise ValueError(f"refr_period {refr_period} outside [0, {R_MAX}]")
        self.thresh = thresh
        self.v_reset = v_reset
        self.leak_shift = leak_shift
        self.syn_shift = syn_shift
        self.refr_period = refr_period
        self.leak_en = bool(leak_en)


class LIFCore:
    """One time-multiplexed LIF core: N_AXONS x N_NEURONS 4-bit crossbar.

    weights: list [n_axons][n_neurons] of plain ints in [-8, +7] (E1).
    tile_offset: added to emitted neuron ids (multi-pass tiling, E5/E9).
    poisoned_words: word indices flagged uncorrectable by ECC; every
    weight in such a word contributes zero (E10, fail-operational).
    """

    def __init__(self, n_neurons, n_axons, weights, config, tile_offset=0):
        _check_int("n_neurons", n_neurons)
        _check_int("n_axons", n_axons)
        _check_int("tile_offset", tile_offset)
        if n_neurons < 1 or n_axons < 1:
            raise ValueError("n_neurons and n_axons must be >= 1")
        if len(weights) != n_axons:
            raise ValueError(f"expected {n_axons} weight rows, got {len(weights)}")
        for a, row in enumerate(weights):
            if len(row) != n_neurons:
                raise ValueError(f"weight row {a} has {len(row)} entries, "
                                 f"expected {n_neurons}")
            for j, w in enumerate(row):
                _check_int(f"weight[{a}][{j}]", w)
                if not W_MIN <= w <= W_MAX:
                    raise ValueError(f"weight[{a}][{j}] = {w} outside "
                                     f"[{W_MIN}, {W_MAX}] (E1)")
        self.n_neurons = n_neurons
        self.n_axons = n_axons
        self.weights = [list(row) for row in weights]
        self.config = config
        self.tile_offset = tile_offset
        self.poisoned_words = set()
        self.v = [0] * n_neurons  # post-STATE_CLR state (spec section 3)
        self.r = [0] * n_neurons

    # -- state access (N_ADDR/N_DATA port model) ---------------------------

    def reset_state(self):
        """CTRL.STATE_CLR: zero all neuron state."""
        self.v = [0] * self.n_neurons
        self.r = [0] * self.n_neurons

    def get_state(self, j):
        return self.v[j], self.r[j]

    def set_state(self, j, v, r=0):
        """Debug/state-restore write; validated like the state word."""
        _check_int("v", v)
        _check_int("r", r)
        if not V_MIN <= v <= V_MAX:
            raise ValueError(f"v {v} outside [{V_MIN}, {V_MAX}]")
        if not 0 <= r <= R_MAX:
            raise ValueError(f"r {r} outside [0, {R_MAX}]")
        self.v[j] = v
        self.r[j] = r

    # -- ECC hook (E10) ----------------------------------------------------

    def word_index(self, axon, j):
        """Weight SRAM word index of W[axon][j] (spec section 5)."""
        return (axon * self.n_neurons + j) // WEIGHTS_PER_WORD

    def poison_word(self, word):
        """Mark a weight word uncorrectable (double-bit ECC error model)."""
        self.poisoned_words.add(word)

    # -- event processing (E1..E8) -----------------------------------------

    def synaptic_event(self, axon):
        """Consume one input spike event; return emitted spike ids in order.

        Implements E1..E5 with the E8 ascending-index scan.
        """
        _check_int("axon", axon)
        if not 0 <= axon < self.n_axons:
            raise ValueError(f"axon {axon} outside [0, {self.n_axons}) "
                             "(hardware drops and counts CNT_AXON_OOR)")
        cfg = self.config
        spikes = []
        for j in range(self.n_neurons):
            if self.r[j] > 0:  # (E7) refractory gate: no state change
                continue
            if self.word_index(axon, j) in self.poisoned_words:
                c = 0  # (E10) uncorrectable word: zero substitution
            else:
                c = self.weights[axon][j] * (1 << cfg.syn_shift)  # (E1)(E2)
            v = sat16(self.v[j] + c)  # (E3)
            if v >= cfg.thresh:  # (E4) checked after the update
                spikes.append(self.tile_offset + j)  # (E5) emitted id
                self.v[j] = cfg.v_reset  # (E5)
                self.r[j] = cfg.refr_period  # (E5)
            else:
                self.v[j] = v
        return spikes

    def tick(self):
        """Consume one TICK event: refractory countdown and leak (E6, E7).

        Never emits spikes (spec section 4.2).
        """
        cfg = self.config
        for j in range(self.n_neurons):
            if self.r[j] > 0:  # (E7) countdown
                self.r[j] -= 1
            if cfg.leak_en:  # (E6) leak applies regardless of R
                self.v[j] = leak_value(self.v[j], cfg.leak_shift)

    def run_frames(self, frames):
        """Convenience driver: frames is a list of timesteps, each a list
        of input axon ids (in arrival order). Each timestep is processed
        as its spike events in order followed by one TICK (E8). Returns
        the per-timestep list of emitted spike ids.
        """
        out = []
        for timestep in frames:
            spikes = []
            for axon in timestep:
                spikes.extend(self.synaptic_event(axon))
            self.tick()
            out.append(spikes)
        return out
