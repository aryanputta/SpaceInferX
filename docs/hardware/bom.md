# Bill of Materials — SpaceInferX Compute Module (Prototype)

**Rev:** 0.1 (Design Phase — pre-procurement)  
**Date:** 2026-05-18  
**Budget:** $5,000 research allocation  
**Note:** Commercial-off-the-shelf radiation-tolerant parts used where available. Engineering Grade (non-flight-screened) acceptable for ground prototype validation.

---

## Processor Subsystem

| Item | Part Number | Qty | Unit Cost (Eng Grade) | Extended | Source |
|------|------------|-----|----------------------|----------|--------|
| RAD5545 Quad-Core LEON4FT | BAE-RAD5545-CCGA | 1 | $2,800 | $2,800 | BAE Systems direct |
| Decoupling cap 100nF, 50V, X5R | GRM21BR61H104KE14L | 20 | $0.10 | $2.00 | DigiKey |
| Decoupling cap 10uF, 10V, X5R | GRM31CR61A106KE69L | 5 | $0.30 | $1.50 | DigiKey |

**Subtotal: $2,803.50**

> Note: RAD5545 is export-controlled (ITAR). For academic prototype, use GR740 evaluation board ($1,200, available through ESA distribution) — same LEON4FT core, lower radiation tolerance, no ITAR.

**Prototype alternative: Aeroflex Gaisler GR740 Dev Board — $1,200**

---

## Memory Subsystem

| Item | Part Number | Qty | Unit Cost | Extended | Source |
|------|------------|-----|-----------|----------|--------|
| MRAM 16Mbit (for KV cache pages) | Everspin MR4A16BUYS45 | 16 | $28.00 | $448 | DigiKey |
| RadHard SRAM 4Mbit (weight buffer) | Integrated Device 71V416SA10 | 4 | $45.00 | $180 | IDT/Renesas direct |
| NOR Flash 256Mbit (model storage) | Infineon S29GL256S10TFI010 | 4 | $12.00 | $48 | DigiKey |

**Subtotal: $676**

> MRAM addresses the KV cache SEU problem directly — magnetic storage cells are immune to radiation-induced bit flips. This is the core architectural decision from the fault sweep results.

---

## FPGA (ECC Controller + Accelerator)

| Item | Part Number | Qty | Unit Cost | Extended | Source |
|------|------------|-----|-----------|----------|--------|
| RTG4 FPGA (150K LE, flash-based) | Microchip M2GL150TS-FGG1152I | 1 | $420 | $420 | Microchip direct |
| FPGA decoupling kit | — | 1 | $15 | $15 | DigiKey |

**Subtotal: $435**

> RTG4 uses flash-based configuration — no SRAM configuration cells to upset. Eliminates need for TMR (triple modular redundancy) on FPGA configuration, reducing design complexity.

---

## Power Management

| Item | Part Number | Qty | Unit Cost | Extended | Source |
|------|------------|-----|-----------|----------|--------|
| DC-DC converter 48V→5V, 10W | Vicor DCM48AP12T400A65 | 1 | $85 | $85 | Vicor direct |
| LDO 5V→3.3V, 1.5A (rad-hard) | Intersil ISL75051SEH | 1 | $38 | $38 | DigiKey |
| LDO 5V→1.8V, 1A | Texas Instruments TPS7A3301KTTT | 1 | $22 | $22 | DigiKey |
| Power monitor (current/voltage) | Texas Instruments INA226AIDGST | 3 | $4.50 | $13.50 | DigiKey |
| TVS protection diode array | Vishay SMDA05C | 5 | $1.20 | $6.00 | DigiKey |

**Subtotal: $164.50**

---

## Thermal Management

| Item | Part Number | Qty | Unit Cost | Extended | Source |
|------|------------|-----|-----------|----------|--------|
| Temperature sensor I2C | TI TMP175AIDR | 3 | $2.80 | $8.40 | DigiKey |
| Thermal interface pad | Bergquist GP3000S3010 | 1 sheet | $18 | $18 | DigiKey |
| Indium foil 0.1mm | Indium Corp IN-FOIL-0.1 | 5 cm² | $12 | $12 | Indium Corp |
| Thermal grease (Dow TC5026) | Dow TC5026 | 10g | $15 | $15 | DigiKey |
| Radiator blank Al 6061 (black anodize) | McMaster 8975K21 | 1 | $22 | $22 | McMaster-Carr |
| Heater resistor 5W, 47Ω (cold survival) | Vishay RH005R470F | 2 | $3.50 | $7.00 | DigiKey |

**Subtotal: $82.40**

---

## Communication / Interface

| Item | Part Number | Qty | Unit Cost | Extended | Source |
|------|------------|-----|-----------|----------|--------|
| SpaceWire interface PHY | STAR-Dundee SpW-USB-Brick | 1 | $290 | $290 | STAR-Dundee (ground test) |
| UART to USB (debug) | FTDI FT232RQ | 1 | $4.50 | $4.50 | DigiKey |
| Ethernet PHY (ground test interface) | Microchip KSZ8081RNBIA | 1 | $3.20 | $3.20 | DigiKey |
| SMA connector (SpW) | Amphenol 132289 | 4 | $3.80 | $15.20 | DigiKey |

**Subtotal: $312.90**

---

## PCB and Mechanical

| Item | Qty | Unit Cost | Extended | Source |
|------|-----|-----------|----------|--------|
| PCB fabrication (8-layer, 100×100mm, ENIG) | 3 boards | $180 | $540 | OSH Park / 4PCB |
| Standoffs M2.5 × 5mm Al | 20 | $0.40 | $8.00 | McMaster-Carr |
| CubeSat PC-104 form adapter | 1 | $45 | $45 | Pumpkin Inc |
| Conformal coating (Humiseal 1B31, aerosol) | 1 can | $28 | $28 | DigiKey |
| Kapton tape 1/2" (MLI layer test) | 1 roll | $12 | $12 | DigiKey |

**Subtotal: $633**

---

## Test Equipment (One-Time)

| Item | Qty | Unit Cost | Extended | Source |
|------|-----|-----------|----------|--------|
| JTAG debugger (Lauterbach TRACE32 academic) | 1 | $0 (academic license) | $0 | Lauterbach |
| Vacuum chamber (rental, 2 days) | 2 days | $800 | $1,600 | [Local university lab] |
| Radiation source access (Co-60 gamma, 1 krad test) | 1 session | $500 | $500 | [University reactor lab] |

**Subtotal: $2,100** (if purchased; $500 for gamma test only)

---

## Budget Summary

| Category | Cost |
|----------|------|
| Processor (GR740 dev board, no ITAR) | $1,200 |
| Memory (MRAM + SRAM + NOR Flash) | $676 |
| FPGA (RTG4) | $435 |
| Power management | $165 |
| Thermal management | $82 |
| Communication / interface | $313 |
| PCB and mechanical | $633 |
| **Hardware subtotal** | **$3,504** |
| Radiation test (gamma) | $500 |
| Vacuum thermal cycling (rental) | $800 |
| Contingency (10%) | $380 |
| **Total** | **$5,184** |

**Note:** $184 over budget. Options:
1. Use Raspberry Pi Compute Module 4 for initial software validation (eliminates $1,200 processor cost) — run all software experiments, then procure GR740 for radiation testing
2. Skip formal vacuum thermal test ($800) and substitute thermal chamber at Rutgers ECE lab
3. Defer RTG4 ($435) and use COTS FPGA (Intel Cyclone IV, $15) for ECC controller prototype

**Recommended path:** Software-first on RPI CM4 → validate all Track 1 experiments → procure GR740 + MRAM for radiation testing within $5,000.
