# NPU register map v0.1

<!-- GENERATED FILE - edit regmap/regmap.yaml and run regmap/generate.py -->

Bus: 32-bit word-aligned peripheral bus (RV32 manager, APB-class bridge). Address space: 12-bit byte
offsets within the block window; registers are 32-bit,
word-aligned. Access codes: RO read-only, RW read-write, WO write-only,
W1C write-1-to-clear, SC self-clearing.

Normative register list: docs/10-npu-mvp-spec.md section 10; the
sync test (sw/tests/test_regmap.py) enforces the alignment.

## sys - Identification, control and status

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x000 | ID | RO | 0x4E505531 | Identity constant, ASCII "NPU1" (vendor byte 0x4E "N" + device code); fixed discovery word at the block base |
| 0x004 | VERSION | RO | 0x00000001 | Spec/regmap version |
| 0x008 | SCRATCH | RW | 0x00000000 | Read/write test register, no side effects |
| 0x00C | CTRL | RW | 0x00000008 | NPU global control |
| 0x010 | STATUS | RO | 0x00000006 | NPU global status; sticky bits b3..b6 cleared via STATUS_CLR |
| 0x014 | STATUS_CLR | W1C | 0x00000000 | Write-1-to-clear mask for STATUS b3..b6 |

### CTRL fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | EN | RW | Core enable; 0 gates the event pipeline |
| 1 | STATE_CLR | SC | Zero all neuron state words (hardware sequencer, BUSY while running); self-clears |
| 2 | SOFT_RST | SC | Flush queues and pipeline, configuration retained; self-clears |
| 3 | SCRUB_EN | RW | Background ECC scrubber enable (walks weight SRAM while the input queue is empty) |

### STATUS fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | BUSY | RO | Event processing, STATE_CLR sweep or scrub write in progress |
| 1 | EVQ_IN_EMPTY | RO | Input event queue empty |
| 2 | EVQ_OUT_EMPTY | RO | Output event queue empty |
| 3 | SYNC_DONE | RO | Sticky: SYNC barrier consumed and echoed; frame output complete |
| 4 | ERR_CFG | RO | Sticky: out-of-range configuration or config write while BUSY |
| 5 | DED_SEEN | RO | Sticky: uncorrectable (double-bit) ECC error observed (see FAULT_ADDR) |
| 6 | OVF_SEEN | RO | Sticky: at least one software-port event dropped at a full input queue (see CNT_EVQ_OVF) |

## cfg - Core-global configuration, loaded per pass (docs/10 section 6)

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x020 | CFG_NEUR | RW | 0x00000200 | Active neuron count for the pass |
| 0x024 | CFG_AXON | RW | 0x00000200 | Valid axon id bound |
| 0x028 | CFG_THRESH | RW | 0x00000100 | Firing threshold THETA (E4) |
| 0x02C | CFG_VRESET | RW | 0x00000000 | Post-spike reset potential (E5) |
| 0x030 | CFG_LEAK | RW | 0x00000003 | Leak shift S_LEAK (E6) |
| 0x034 | CFG_SYNSHIFT | RW | 0x00000000 | Synaptic shift S_SYN (E2) |
| 0x038 | CFG_REFR | RW | 0x00000000 | Refractory period T_REFR (E5, E7) |
| 0x03C | CFG_FLAGS | RW | 0x00000002 | Mode flags |

### CFG_NEUR fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 10:0 | CNT | RW | Neurons swept per event, [1, N_NEURONS]; out of range latches ERR_CFG |

### CFG_AXON fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 10:0 | CNT | RW | Events with axon id >= CFG_AXON are dropped and counted (CNT_AXON_OOR) |

### CFG_THRESH fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 15:0 | THETA | RW | Signed threshold, [1, +32767]; must be positive |

### CFG_VRESET fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 15:0 | VRESET | RW | Signed reset potential; must be below THETA |

### CFG_LEAK fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 3:0 | S_LEAK | RW | Right-shift applied to the potential magnitude per tick, [0, 15] |

### CFG_SYNSHIFT fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 2:0 | S_SYN | RW | Left-shift applied to decoded weights, [0, 7] |

### CFG_REFR fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 3:0 | T_REFR | RW | Ticks of post-spike gating, [0, 15]; 0 disables refractory |

### CFG_FLAGS fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | TS_EN | RW | Append a 16-bit timestamp word to every AER event (docs/10 section 7.3) |
| 1 | LEAK_EN | RW | Enable leak on TICK events (E6) |

## pass - Multi-pass sequencing (docs/10 section 9)

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x040 | PASS_TILE_OFF | RW | 0x00000000 | Neuron-tiling offset (E9) |
| 0x044 | W_BASE | RW | 0x00000000 | QSPI byte address of the current pass weight slice |
| 0x048 | PASS_ID | RW | 0x00000000 | Software pass bookkeeping |

### PASS_TILE_OFF fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 9:0 | OFF | RW | TILE_OFF added to emitted neuron ids |

### PASS_ID fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 7:0 | NUM | RW | Pass number, software-defined |

## mem - Weight SRAM load port and neuron state access

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x050 | W_ADDR | RW | 0x00000000 | Weight SRAM word index; auto-increments on W_DATA_HI commit |
| 0x054 | W_DATA_LO | WO | 0x00000000 | Weight word bits [31:0], staged |
| 0x058 | W_DATA_HI | WO | 0x00000000 | Weight word bits [63:32]; write commits the 64-bit word (ECC bits generated in hardware) |
| 0x060 | N_ADDR | RW | 0x00000000 | Neuron index for state access |
| 0x064 | N_DATA | RW | 0x00000000 | Neuron state word at N_ADDR; debug and pass state save/restore |

### N_DATA fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 15:0 | V | RW | Membrane potential, signed |
| 19:16 | R | RW | Refractory countdown |

## fault - Fault counters and injection hooks (docs/10 section 11)

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x070 | CNT_SEC | RO | 0x00000000 | Corrected single-bit ECC events |
| 0x074 | CNT_DED | RO | 0x00000000 | Uncorrectable double-bit ECC events (E10 zero-substitution applied) |
| 0x078 | CNT_EVQ_OVF | RO | 0x00000000 | Software-port event drops on full input queue (aer_fifo sticky drop counter) |
| 0x07C | CNT_AXON_OOR | RO | 0x00000000 | Events dropped for axon id >= CFG_AXON |
| 0x080 | FAULT_ADDR | RO | 0x00000000 | Weight SRAM word index of the last double-bit detection |
| 0x084 | ECC_INJ | WO | 0x00000000 | ECC error-injection hook (verification builds; netlist-audited out of flight builds) |
| 0x088 | FAULT_CLR | W1C | 0x00000000 | Clear the fault counters; one bit per fault-block register in offset order from 0x70, bits [31:5] ignored. Bits 5 and up are deliberately not fields here: hw/rtl/pilot_top.v allocates b5 for that build's pilot-only CNT_TMR clear, b6 for CNT_EVQ_OUT_OVF and b7 for CNT_EVQ_PAR (its section 5), and this block ignores all three, so a host that writes the pilot's clear-everything mask of 0xFF is portable across both. CORRECTED 2026-09-09: this description said that portable mask was 0x3F. That was true only while b5 was the sole pilot bit; hw/rtl/pilot_top.v line 255 has read 0xFF since CNT_EVQ_PAR was added (docs/30), and the superseded 0x3F is left standing in this sentence rather than deleted so the correction is traceable. A host that still writes 0x3F clears b0..b5 and leaves CNT_EVQ_OUT_OVF and CNT_EVQ_PAR standing. Declaring these bits would also require CNT_TMR, CNT_EVQ_OUT_OVF and CNT_EVQ_PAR registers in this map, in docs/10 section 10 and in hw/rtl/npu_regbank.v, because one clear bit per fault-block register is a checked convention (sw/tests/test_regmap.py) |

### ECC_INJ fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | SINGLE | SC | Flip one bit on the next W_DATA commit |
| 1 | DOUBLE | SC | Flip two bits on the next W_DATA commit |

### FAULT_CLR fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 0 | CNT_SEC | W1C | Clear CNT_SEC (0x70) |
| 1 | CNT_DED | W1C | Clear CNT_DED (0x74) |
| 2 | CNT_EVQ_OVF | W1C | Clear CNT_EVQ_OVF (0x78); also re-exported to the input queue drop counter |
| 3 | CNT_AXON_OOR | W1C | Clear CNT_AXON_OOR (0x7C) |
| 4 | FAULT_ADDR | W1C | Clear FAULT_ADDR (0x80) |

## aer - AER queue access and mesh addressing (docs/10 sections 7, 8)

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x090 | EVQ_STAT | RO | 0x00000000 | Event queue fill levels |
| 0x094 | EVQ_IN | WO | 0x00000000 | Software event injection, 16-bit event word; drops on full and counts (CNT_EVQ_OVF) |
| 0x098 | EVQ_OUT | RO | 0x00000000 | Pop one output event |
| 0x09C | NODE_ID | RW | 0x00000000 | Mesh node address (docs/10 section 8) |

### EVQ_STAT fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 7:0 | IN_FILL | RO | Input queue occupancy |
| 15:8 | OUT_FILL | RO | Output queue occupancy |

### EVQ_OUT fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 15:0 | EVENT | RO | Event word, valid when VALID = 1 |
| 31 | VALID | RO | A word was popped; 0 = queue was empty |

### NODE_ID fields

| Bits | Field | Access | Description |
|---|---|---|---|
| 3:0 | NID | RW | This node's mesh address; frozen link-word field |
