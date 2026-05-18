# Thermal Design — SpaceInferX Passive Cooling Analysis

## Overview

Space-analog compute modules cannot use convective cooling. Heat dissipation is
exclusively radiative — Stefan-Boltzmann emission from the module surface to deep space.
This document derives the thermal budget, radiator sizing, and orbital temperature profile.

---

## Thermal Physics

### Radiative Power Emission
```
P_out = ε · σ · A · T⁴

ε = surface emissivity (0.85 for black anodized aluminum)
σ = 5.670 × 10⁻⁸ W/(m²·K⁴)
A = radiator area (m²)
T = surface temperature (K)
```

### Heat Input (LEO, worst case: full sun)
```
P_solar  = 1361 · α · A_cross    (direct solar)
P_albedo = 1361 · 0.30 · α · A_cross · 0.5  (Earth albedo)
P_earth  = 237 · ε_body · A_cross  (Earth IR)

α = solar absorptivity = 0.15 (white paint or MLI blanket)
A_cross = cross-sectional area facing sun
```

### Energy Balance
```
C · dT/dt = P_solar + P_albedo + P_earth + P_compute - P_out

C = m · c_p = 1.2 kg × 900 J/(kg·K) = 1080 J/K
```

---

## 1U Module Baseline (100×100×100 mm)

| Parameter | Value |
|-----------|-------|
| Radiator face area | 100 cm² (10⁻² m²) |
| Cross-section (sun-facing) | 100 cm² |
| Total surface | 600 cm² |
| Module mass | 1.2 kg |
| Thermal mass | 1080 J/K |

---

## Steady-State Temperature by Scenario

Using `P_out = P_in + P_compute` → solve for T:

```python
T = ((P_in + P_compute) / (ε · σ · A)) ** 0.25
```

| Scenario | P_in (W) | P_compute (W) | T_eq (°C) |
|----------|----------|---------------|-----------|
| Full sun, idle (1.5W) | 2.1 | 1.5 | ~48 |
| Full sun, active (5W) | 2.1 | 5.0 | ~82 |
| Eclipse, active (5W) | 0.2 | 5.0 | ~74 |
| Eclipse, idle (1.5W) | 0.2 | 1.5 | ~30 |

**Critical result:** Full sun + full compute load reaches 82°C — just below the 85°C limit.
Thermal throttle begins at 70°C, meaning the module will throttle 15-20% under worst-case
combined conditions (SAA crossing in full sun at maximum inference load).

---

## Radiator Sizing

Minimum radiator area to maintain T < 85°C under full load, full sun:

```
A_min = (P_in + P_compute) / (ε · σ · T_max⁴)
      = (2.1 + 5.0) / (0.85 × 5.67e-8 × 358⁴)
      = 7.1 / (0.85 × 5.67e-8 × 1.64×10¹⁰)
      = 7.1 / 7.90
      = 0.0089 m²  =  89 cm²
```

The 1U form factor provides 100 cm². **Margin: 12%.**

For a 10W compute module (dual-1U), required radiator area = 133 cm² → must use a
deployable radiator panel or 2U form factor with dedicated radiator face.

---

## LEO Orbital Temperature Profile

Eclipse fraction at 400km: ~35% of orbit (38 min eclipse per 92 min pass)

Temperature oscillation per orbit:
- Max (full sun phase): ~80-82°C (near throttle threshold)
- Min (eclipse, compute off): ~-15°C to -20°C

**Delta-T per orbit: ~95-100°C** — this is the thermal fatigue driver.
At 16 orbits/day, 365 days/year, 5-year mission: ~29,200 thermal cycles.
Solder joint design must account for this (low-cycle fatigue criterion).

---

## Thermal Interface Materials

| Interface | Material | Conductivity | Purpose |
|-----------|----------|-------------|---------|
| Die → spreader | Indium foil (0.1mm) | 80 W/(m·K) | Fills die surface roughness |
| Spreader → PCB | Bergquist GP3000 pad | 3.0 W/(m·K) | Compliant electrical isolation |
| PCB → radiator | Thermal grease (Dow TC5026) | 2.0 W/(m·K) | Fills mechanical gap |
| Radiator finish | Black anodized Al 6061 | ε = 0.85 | Maximizes IR emission |

Total thermal resistance (die → radiator outer): ~4.2°C/W
At 5W TDP: 21°C rise from junction to radiator surface → junction at ~103°C in worst case.

**Mitigation:** Place active thermal management via throttle at 70°C (radiator surface),
which corresponds to ~91°C junction — within safe range for RAD5545 (junction limit 125°C).

---

## Multi-Layer Insulation (MLI) Blanket

MLI is used on all faces except the dedicated radiator face.
- Reduces solar absorptivity of body faces to α_eff ≈ 0.03
- Reduces effective emissivity of body faces to ε_eff ≈ 0.02-0.03
- Net effect: limits heat input on non-radiating faces

MLI specification: 20-layer (0.25 mil Kapton + double-aluminized Mylar)
Effective ε with blanket: 0.02 (vs 0.10 bare aluminum)

With MLI on all body faces: P_earth_IR contribution drops from 0.48W → 0.10W.
Reduces worst-case steady-state temperature by ~3-4°C — enough to restore full margin.

---

## Thermal Control Strategy

1. **Primary:** Passive radiation to deep space via dedicated radiator face
2. **Sensor loop:** Three TMP175 sensors (processor, memory, radiator)
3. **Throttle trigger:** Processor throttle at radiator T > 70°C
4. **Emergency:** Inference task pause at T > 82°C, resume at T < 65°C
5. **Eclipse:** Maintain low-power inference mode (idle weights in MRAM, no active prefill)

### Thermal State Machine (implemented in thermal_model.py)
```
COLD  (<-20°C): Heater resistor ON (0.5W), no inference
NOMINAL (-20 to 70°C): Full inference, no throttle
WARM (70-82°C): Linear throttle (0-100% reduction over 12°C range)
HOT (>82°C): Inference suspended, store partial KV cache to MRAM
```

---

## Thermal Fatigue — Solder Joint Life Estimate

Using Coffin-Manson relationship:
```
N_f = C · (ΔT)^(-n)
ΔT = 95°C per orbit (conservative)
n = 1.9 (eutectic solder)
C = 1.2 × 10⁶ (empirical constant)

N_f = 1.2e6 / (95^1.9) = 1.2e6 / 5890 ≈ 204 cycles to 50% failure
```

LEO mission at 16 orbits/day × 1825 days (5 years) = **29,200 cycles required.**

**Result: Standard eutectic solder joints do not meet 5-year LEO life.**

**Mitigation:**
- Use SAC305 lead-free solder (higher fatigue life by ~2x): ~400 cycles
- Still insufficient. Add underfill on BGA packages (RAD5545 CCGA)
- CCGA (ceramic column grid array) uses compliant gold-plated copper columns — designed for space thermal cycling. Inherently more fatigue-resistant than BGA.
- With CCGA + underfill: > 50,000 cycle fatigue life (vendor data)

---

## Summary: Thermal Feasibility

| Check | Status |
|-------|--------|
| Steady-state T < 85°C (full load, full sun) | PASS (82°C, 3°C margin) |
| Radiator area sufficient (1U face) | PASS (100 cm² vs 89 cm² required) |
| Eclipse cold survival > -40°C | PASS (~-15°C minimum) |
| Thermal fatigue (5-year LEO) | PASS with CCGA packages + underfill |
| Throttle headroom at 70°C | 15% headroom before full-load throttle |

The 1U form factor is thermally viable for a 5W processor at LEO-400km.
Exceeding 5W TDP requires a deployable radiator or 2U form factor.
