# Component Selection — SpaceInferX Compute Module

## Design Constraints

| Parameter | Requirement | Rationale |
|-----------|-------------|-----------|
| TID tolerance | > 100 krad(Si) | LEO 5-year mission dose |
| SEL immunity | Full latch-up immune | No power cycling in orbit |
| Operating temp | -40°C to +85°C | Passive cooling in LEO eclipse/sun cycle |
| Power budget | < 5W total | Single face radiator (100×100mm) limit |
| Form factor | 1U CubeSat PCB stack | Standard launcher compatibility |
| Memory ECC | SECDED minimum | Corrects SEU in SRAM/DRAM |

---

## Processor

### Selected: BAE Systems RAD5545
- Architecture: Quad-core LEON4FT (SPARC V8)
- Frequency: 400 MHz per core
- TID: > 1 Mrad(Si)
- SEL: Immune (SOI process)
- SEU: EDAC on all internal registers
- Power: ~3W at full load (all 4 cores)
- Package: CCGA 624
- Interface: SpaceWire, MIL-STD-1553, SPI, I2C, UART

**Why:** Only radiation-hardened quad-core processor with sufficient MIPS for TinyLlama Q4 inference at useful throughput. The LEON4FT implements hardware register file scrubbing — critical for long-duration inference tasks.

### Alternative: Cobham Gaisler GR740
- Architecture: Quad-core LEON4FT
- Frequency: 250 MHz
- TID: > 300 krad(Si)
- Lower cost, lower radiation tolerance — suitable for shorter missions or testing

---

## Memory — Primary (KV Cache Storage)

### Selected: Everspin MR4A16B MRAM
- Capacity: 16 Mbit (2 MB per device) — use 16× for 32MB
- Access time: 35ns (comparable to SRAM)
- TID: > 1 Mrad(Si)
- SEU: Intrinsically immune (magnetic storage, not charge)
- Power: 65mW active per device
- **Key property: Non-volatile + radiation-tolerant = no scrubbing required**

**Why:** KV cache bit flips are the primary inference quality failure mode (measured at BER 1e-4 threshold). MRAM's magnetic storage mechanism is immune to ionizing radiation SEU — eliminates the KV cache fault injection problem entirely for stored pages.

### Alternative: Integrated Device Technology 71V416 SRAM (radiation-hardened)
- Capacity: 4 Mbit per device
- TID: > 300 krad(Si)
- Requires SECDED ECC scrubber (add Microsemi SmartFusion2 SoC as ECC controller)
- Use when cost > radiation tolerance

---

## Memory — Secondary (Weight Storage)

### Selected: Cypress CYRS1544AV18 RadHard SRAM
- Capacity: 144 Mbit, 18-bit wide (ECC integrated)
- TID: > 300 krad(Si)
- SEL: Immune
- Used for model weight storage (TinyLlama Q4 ≈ 638 MB → use NOR Flash for larger models)

### NOR Flash for Model Weights: Cypress S29GL256S RadHard
- Capacity: 256 Mbit per device — stack 4× for 128MB model buffer
- TID: > 100 krad(Si)
- Read bandwidth: ~60 MB/s sufficient for Q4 weight streaming
- Non-volatile: survives power cycling, no re-upload needed after reset

---

## FPGA (Hardware Accelerator + ECC Controller)

### Selected: Microchip RT4G150 (RTG4)
- Capacity: 150K logic elements
- TID: > 100 krad(Si)
- SEL: Immune (flash-based — configuration not lost on SEU)
- SEU: No configuration upset (unlike SRAM FPGAs)
- Power: ~2W at partial utilization
- Use: ECC scrubber, SpaceWire bridge, attention kernel acceleration

**Why:** SRAM-based FPGAs (Xilinx) require continuous scrubbing to prevent configuration bit upsets. Flash-based RTG4 eliminates that overhead — simpler firmware, lower power.

---

## Power Management

### Selected: Vicor DCM48AP12T400A65
- Input: 24–48V (solar panel bus)
- Output: 12V / 3.3V / 1.8V regulated
- TID: > 50 krad(Si) (tested)
- Efficiency: 91% at full load
- Heat to manage: 0.45W at 5W load (9% loss → 0.45W dissipation)

### Radiation-Hard LDO: Intersil ISL75051 (5V → 3.3V, 1.5A)
- TID: > 100 krad(Si)
- PSRR: 65 dB — clean power for ADC + reference circuits

---

## Interface / Communication

### SpaceWire Router: Cobham Gaisler GRSPW2
- Protocol: ECSS-E-50-12A SpaceWire (2Mbit–400Mbit/s)
- Use: Inter-module KV cache transfer between SpaceInferX nodes
- TID: > 300 krad(Si)

### Temperature Sensors: Texas Instruments TMP175 (space-screened)
- 12-bit, I2C, -55°C to +125°C
- Place at: processor die edge, MRAM array, radiator backside
- Used by thermal manager to trigger inference throttle

---

## PCB Design Requirements

| Parameter | Specification |
|-----------|--------------|
| Material | Isola IS410 (Rogers 4350B for RF sections) |
| Layer count | 8-layer minimum (power/ground planes for EMI) |
| Trace spacing | 200µm minimum (corona discharge margin at altitude) |
| Via fill | Epoxy-filled + capped (outgassing prevention) |
| Conformal coating | Humiseal 1B31 (radiation-stable acrylic) |
| Component derating | 50% voltage, 75% current (ECSS-Q-ST-30 Class 2) |
| Outgassing | All materials MIL-STD-1246C compliant |

---

## Radiation Component Selection Rationale

The core principle: avoid SRAM-based latches in any path that carries KV cache data.

- Processor: SOI CMOS → no SEL, register file scrubbed in hardware
- Primary memory: MRAM → magnetic storage, SEU-immune
- FPGA: Flash-based → no configuration upset
- Flash storage: NOR (single transistor cell) → higher radiation tolerance than NAND

This selection minimizes the fault modes that the KV cache BER sweep identified as catastrophic (page-level, BER > 1e-4). With MRAM, the catastrophic threshold no longer applies to stored pages — only to in-flight computation in the processor pipeline.
