"""Multi-pass network runner over the bit-exact LIF core golden model.

Models the multi-pass execution concept of docs/10-npu-mvp-spec.md
section 9: one physical core of at most (core_neurons x core_axons),
larger networks executed as a sequence of passes. Two pass dimensions,
exactly as specified:

  1. layer-serial — one layer (or layer tile) per pass, output spikes of
     layer L replayed as input events of layer L+1 in canonical order;
  2. output-neuron tiling (E9) — a layer wider than the core is split
     into ordered contiguous tiles; each pass replays the identical input
     event stream against one tile (PASS_TILE_OFF = tile base) and the
     per-event emissions are concatenated in tile order.

The axon dimension is not splittable in v0.1 (spec section 9 limitation);
the runner enforces fan-in <= core_axons. Tiled layer width is capped at
1024 = 2^10 (spec section 9 limitation): the last tile's base + width
must fit the frozen 10-bit event-word ID field, so the runner refuses
wider layers at construction.

Integer-only, like everything in the golden path.
"""

from .lif_core import EVENT_ID_SPAN, LIFCore


class LayerSpec:
    """One fully-connected spiking layer: weights [n_axons][n_neurons]
    plus its LIFConfig (one configuration per pass, spec section 6)."""

    def __init__(self, weights, config):
        if not weights or not weights[0]:
            raise ValueError("layer weights must be a non-empty 2-D list")
        self.weights = weights
        self.config = config
        self.n_axons = len(weights)
        self.n_neurons = len(weights[0])


class NetworkRunner:
    """Executes a stack of LayerSpecs on one core-sized resource."""

    def __init__(self, layers, core_neurons=512, core_axons=512):
        if not layers:
            raise ValueError("need at least one layer")
        for i, layer in enumerate(layers):
            if layer.n_axons > core_axons:
                raise ValueError(
                    f"layer {i} fan-in {layer.n_axons} exceeds core_axons "
                    f"{core_axons}: axon-dimension multi-pass is not "
                    "supported in v0.1 (spec section 9)")
            if layer.n_neurons > EVENT_ID_SPAN:
                raise ValueError(
                    f"layer {i} width {layer.n_neurons} exceeds "
                    f"{EVENT_ID_SPAN}: the last tile's base + width would "
                    "overflow the 10-bit event-word ID field (E9 bound, "
                    "spec section 9)")
            if i > 0 and layers[i - 1].n_neurons != layer.n_axons:
                raise ValueError(
                    f"layer {i} fan-in {layer.n_axons} does not match "
                    f"layer {i - 1} fan-out {layers[i - 1].n_neurons}")
        self.layers = list(layers)
        self.core_neurons = core_neurons
        self.core_axons = core_axons

    def layer_passes(self, layer):
        """Number of neuron-tile passes needed for one layer."""
        return -(-layer.n_neurons // self.core_neurons)

    @property
    def total_passes(self):
        return sum(self.layer_passes(layer) for layer in self.layers)

    def run(self, frames):
        """frames: list of timesteps, each a list of input axon ids in
        arrival order. Returns the final layer's per-timestep spike ids,
        in the canonical (event-order, then scan-order) sequence of E8.
        """
        for layer in self.layers:
            frames = self._run_layer(layer, frames)
        return frames

    def _run_layer(self, layer, frames):
        # One pass per neuron tile: a fresh core-sized configuration and
        # weight slice, the full event stream replayed (spec section 9).
        # Emissions are recorded per (timestep, event) so the tiles can be
        # merged into the canonical single-core order (E9).
        tile_records = []
        for start in range(0, layer.n_neurons, self.core_neurons):
            stop = min(start + self.core_neurons, layer.n_neurons)
            weight_slice = [row[start:stop] for row in layer.weights]
            core = LIFCore(stop - start, layer.n_axons, weight_slice,
                           layer.config, tile_offset=start)
            records = []
            for timestep in frames:
                per_event = [core.synaptic_event(a) for a in timestep]
                core.tick()
                records.append(per_event)
            tile_records.append(records)

        # (E9) canonical merge: for each input event, concatenate the
        # tiles' emissions in tile order — bit-identical to one wide core.
        merged = []
        for t, timestep in enumerate(frames):
            spikes = []
            for k in range(len(timestep)):
                for records in tile_records:
                    spikes.extend(records[t][k])
            merged.append(spikes)
        return merged


def spike_counts(frames, n_neurons):
    """Total emitted spikes per neuron id over all timesteps."""
    counts = [0] * n_neurons
    for timestep in frames:
        for j in timestep:
            counts[j] += 1
    return counts
