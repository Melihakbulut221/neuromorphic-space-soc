# GR801 reference brief summary

Source: Frontgrade Gaisler, "GR801 Product Brief", released April 2026,
status "under development" (https://www.gaisler.com/products/gr801).
All figures below are from the public product brief.

## Overview

GR801 is a radiation-hardened SoC for reliable AI applications in space
(image recognition, autonomous navigation, data analysis). Architecture:
a neuromorphic processing engine (BrainChip Akida 1.0), a single-core
RISC-V RV64GC processor (NOEL-V) for system management, and digital
interfaces.

## Akida neuromorphic accelerator

- Event-based computing to minimize power consumption
- Eight neural processing nodes connected in a mesh network
- Each node contains four convolutional or fully connected engines
- Hardware support for 1, 2, or 4-bit hybrid quantized weights
- Multi-pass processing enables execution of large neural networks
- 3.2 MB RAM private to the Akida unit
- Software: TensorFlow/Keras, Edge Impulse, BrainChip MetaTF, model zoo;
  model-, network-, and OS-agnostic

## NOEL-V processor

- General-purpose RISC-V, RV64GC, single core, fault-tolerant variant
- System management and configuration of the neuromorphic engine

## Memory

- 8 MB on-chip RAM
- QSPI memory controller with 2 chip selects

## Interfaces

- PCIe Gen 3, 1 port x4 (root port and endpoint capable)
- 10/100/1000 Mbit Ethernet (GMII)
- Camera Parallel Interface (CPI), 8 data bits
- SpaceWire router, 4 external ports at 200 Mbps
- 2x CAN FD
- 1x SPI (2 chip selects), 2x I2C, 3x UART, 16x GPIO

## Radiation tolerance and platform

- Technology: STMicroelectronics 28 nm FDSOI
- NOEL-V, on-chip memory, and all buffers protected with error
  correction; Akida memories have fault detection with flexible
  fault handling
- GR801-AS flight model: ESCC9030 screening, TID 50 krad(Si) guaranteed
  by platform, 100 krad(Si) testing planned, SEL TBC
- Package: space-grade thermally enhanced BGA, 23x23 mm, 441 balls,
  1 mm pitch

## Initial scaling observations for a 130 nm retarget

These are starting hypotheses to be confirmed or rejected in the
research phase.

1. Density: 28 nm to 130 nm is roughly a 20x density penalty. The 11.2 MB
   of on-chip SRAM alone is far beyond any realistic 130 nm open-PDK die.
   The retarget must shrink memory to the hundreds-of-kB class and scale
   the neural fabric accordingly (fewer nodes, smaller engines).
2. The Akida IP is proprietary. This project designs a clean-room
   event-driven SNN fabric that follows the same architectural ideas
   visible in the public brief (event-based processing, low-bit
   quantized weights, mesh of processing nodes, multi-pass execution),
   not the Akida implementation.
3. NOEL-V is available under GPL in GRLIB but is a large RV64GC core in
   VHDL; a small RV32 management core is the realistic equivalent at
   130 nm, and prior project experience shows VHDL cores break the
   fault-injection observability flow.
4. PCIe Gen 3 and Gigabit Ethernet are not realistic at 130 nm with open
   IP and open flows (SerDes, PHY); SpaceWire, CAN, SPI, I2C, UART, GPIO
   are, and they cover the CubeSat-class use cases.
5. FDSOI contributes intrinsic SEL immunity; bulk 130 nm does not, so
   the hardening story must rely on architecture (TMR, ECC, scrubbing,
   monitors) and honest fault-tolerant positioning rather than
   platform-level radiation guarantees.
