"""
Orbital thermal simulation for the SpaceInferX compute module.

Simulates temperature evolution across 3 orbits for each altitude,
computes steady-state equilibrium, and derives minimum radiator area.
Models passive cooling only — no convection, no heat pipes.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.thermal.thermal_model import (
    OrbitalThermalModel,
    ThermalConfig,
    OrbitAltitude,
    ModuleGeometry,
    thermal_summary,
    STEFAN_BOLTZMANN,
)

RESULTS_DIR = Path("results/space_analog")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ORBITS = [
    OrbitAltitude.LEO_400,
    OrbitAltitude.LEO_800,
    OrbitAltitude.MEO,
    OrbitAltitude.GEO,
]

MODULE_TDP_W = 5.0      # RAD5545 quad-core LEON4FT TDP
IDLE_WATTS = 1.5
T_MAX_C = 85.0
T_MAX_K = T_MAX_C + 273.15


def run_orbit(alt: OrbitAltitude) -> dict:
    cfg = ThermalConfig(
        altitude=alt,
        tdp_watts=MODULE_TDP_W,
        idle_watts=IDLE_WATTS,
        geometry=ModuleGeometry(),
    )
    model = OrbitalThermalModel(cfg)

    # Simulate 3 orbits at full compute load
    states_active = model.simulate(n_orbits=3, dt_s=10.0, compute_active=True)
    # Simulate 3 orbits at idle
    states_idle = model.simulate(n_orbits=3, dt_s=10.0, compute_active=False)

    summary_active = thermal_summary(states_active)
    summary_idle = thermal_summary(states_idle)

    # Steady-state estimates
    t_sun_active_k = model.steady_state_temp(MODULE_TDP_W, in_eclipse=False)
    t_eclipse_active_k = model.steady_state_temp(MODULE_TDP_W, in_eclipse=True)
    t_sun_idle_k = model.steady_state_temp(IDLE_WATTS, in_eclipse=False)
    t_eclipse_idle_k = model.steady_state_temp(IDLE_WATTS, in_eclipse=True)

    # Minimum radiator area to stay below T_MAX under full load, full sun
    area_required = model.radiator_area_required(MODULE_TDP_W, T_MAX_K)

    orb = model.orbital

    return {
        "orbit": alt.value,
        "period_min": round(orb.period_s / 60, 1),
        "eclipse_fraction": round(orb.eclipse_fraction, 3),

        "active_load": {
            "t_min_c": round(summary_active["t_min_c"], 1),
            "t_max_c": round(summary_active["t_max_c"], 1),
            "t_mean_c": round(summary_active["t_mean_c"], 1),
            "throttle_min": round(summary_active["throttle_min"], 3),
            "throttle_mean": round(summary_active["throttle_mean"], 3),
            "unsafe_fraction": round(summary_active["unsafe_fraction"], 4),
        },
        "idle_load": {
            "t_min_c": round(summary_idle["t_min_c"], 1),
            "t_max_c": round(summary_idle["t_max_c"], 1),
            "t_mean_c": round(summary_idle["t_mean_c"], 1),
            "throttle_min": round(summary_idle["throttle_min"], 3),
        },
        "steady_state": {
            "full_sun_active_c": round(t_sun_active_k - 273.15, 1),
            "eclipse_active_c": round(t_eclipse_active_k - 273.15, 1),
            "full_sun_idle_c": round(t_sun_idle_k - 273.15, 1),
            "eclipse_idle_c": round(t_eclipse_idle_k - 273.15, 1),
        },
        "radiator_area_required_cm2": round(area_required * 1e4, 1),
        "current_radiator_cm2": round(ModuleGeometry().radiator_area_m2 * 1e4, 1),
        "radiator_adequate": area_required <= ModuleGeometry().radiator_area_m2,
    }


def main():
    print("Orbital Thermal Simulation — SpaceInferX Track 2")
    print("=" * 55)
    print(f"Module TDP: {MODULE_TDP_W}W | Idle: {IDLE_WATTS}W | T_max: {T_MAX_C}°C")
    print(f"Geometry: 1U CubeSat (100×100mm radiator face)")
    print()

    results = []
    for alt in ORBITS:
        print(f"Simulating {alt.value}...")
        r = run_orbit(alt)
        results.append(r)

        ss = r["steady_state"]
        act = r["active_load"]
        print(f"  Period: {r['period_min']:.1f} min | Eclipse: {r['eclipse_fraction']:.1%}")
        print(f"  Steady-state (active): sun={ss['full_sun_active_c']:.1f}°C, eclipse={ss['eclipse_active_c']:.1f}°C")
        print(f"  Sim peak: {act['t_max_c']:.1f}°C | Throttle min: {act['throttle_min']:.2f}")
        print(f"  Radiator needed: {r['radiator_area_required_cm2']:.0f} cm² | Have: {r['current_radiator_cm2']:.0f} cm² | {'OK' if r['radiator_adequate'] else 'INSUFFICIENT'}")
        print()

    out = RESULTS_DIR / "orbital_thermal_sweep.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved: {out}")

    # Design constraint summary
    print("\nDesign Constraints:")
    print("-" * 55)
    for r in results:
        ss = r["steady_state"]
        flag = "PASS" if r["radiator_adequate"] else "FAIL — extend radiator"
        print(f"{r['orbit']:<20} sun_active={ss['full_sun_active_c']:>5.1f}°C  {flag}")


if __name__ == "__main__":
    main()
