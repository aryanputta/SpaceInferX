"""
Orbital thermal model for space-analog compute modules.

Models radiative heat transfer in LEO/MEO/GEO orbits.
No convection — passive cooling only via radiation to deep space.

Physics:
  P_in  = solar_flux * alpha * A_solar + albedo_flux + earth_IR
  P_out = epsilon * sigma * A_radiator * T^4
  C * dT/dt = P_in - P_out - P_compute
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


STEFAN_BOLTZMANN = 5.670374419e-8   # W/(m^2·K^4)
SOLAR_FLUX_LEO = 1361.0             # W/m² (solar constant)
EARTH_ALBEDO = 0.30                 # mean albedo
EARTH_IR_FLUX = 237.0               # W/m² Earth IR emission at LEO


class OrbitAltitude(Enum):
    LEO_400 = "LEO-400km"
    LEO_800 = "LEO-800km"
    MEO = "MEO-20000km"
    GEO = "GEO-36000km"


@dataclass
class ModuleGeometry:
    """Physical dimensions of the compute module."""
    length_m: float = 0.10          # 1U CubeSat = 100mm
    width_m: float = 0.10
    height_m: float = 0.10

    # Surface properties
    solar_alpha: float = 0.15       # solar absorptivity (white paint / MLI)
    epsilon_radiator: float = 0.85  # IR emissivity of radiator face (black anodized Al)
    epsilon_body: float = 0.10      # IR emissivity of non-radiator faces (polished Al)

    @property
    def cross_section_m2(self) -> float:
        return self.length_m * self.width_m

    @property
    def radiator_area_m2(self) -> float:
        return self.length_m * self.width_m

    @property
    def total_surface_m2(self) -> float:
        l, w, h = self.length_m, self.width_m, self.height_m
        return 2 * (l * w + l * h + w * h)


@dataclass
class ThermalConfig:
    altitude: OrbitAltitude = OrbitAltitude.LEO_400
    geometry: ModuleGeometry = field(default_factory=ModuleGeometry)

    # Thermal mass of module
    mass_kg: float = 1.2                # ~1.2kg for a 1U compute module
    specific_heat_j_per_kg_k: float = 900.0  # aluminum structure

    # Operating limits
    t_op_min_c: float = -40.0
    t_op_max_c: float = 85.0
    t_throttle_c: float = 70.0

    # Compute power dissipation
    tdp_watts: float = 5.0              # typical radiation-hard processor TDP
    idle_watts: float = 1.5

    @property
    def thermal_mass_j_per_k(self) -> float:
        return self.mass_kg * self.specific_heat_j_per_kg_k


@dataclass
class OrbitalParameters:
    """Derived orbital parameters by altitude."""
    period_s: float                 # orbital period
    eclipse_fraction: float         # fraction of orbit in eclipse
    solar_flux: float               # effective solar flux W/m²

    @classmethod
    def for_altitude(cls, alt: OrbitAltitude) -> "OrbitalParameters":
        R_EARTH = 6371e3    # m
        MU = 3.986e14       # m^3/s^2

        if alt == OrbitAltitude.LEO_400:
            h = 400e3
        elif alt == OrbitAltitude.LEO_800:
            h = 800e3
        elif alt == OrbitAltitude.MEO:
            h = 20_000e3
        else:  # GEO
            h = 35_786e3

        r = R_EARTH + h
        period = 2 * math.pi * math.sqrt(r**3 / MU)

        # Eclipse fraction: fraction of orbit behind Earth's shadow
        # Approximation for circular orbit, worst-case (equatorial)
        if h >= 35_000e3:
            eclipse_frac = 0.0   # GEO: essentially no eclipse
        else:
            sin_rho = R_EARTH / r
            rho = math.asin(sin_rho)
            eclipse_frac = rho / math.pi

        return cls(
            period_s=period,
            eclipse_fraction=eclipse_frac,
            solar_flux=SOLAR_FLUX_LEO,
        )


@dataclass
class ThermalState:
    t_seconds: float = 0.0
    temp_c: float = 20.0
    temp_k: float = 293.15
    p_in_w: float = 0.0
    p_out_w: float = 0.0
    p_compute_w: float = 0.0
    in_eclipse: bool = False
    throttle_factor: float = 1.0
    in_safe_range: bool = True


class OrbitalThermalModel:
    """
    Simulates thermal evolution of a passive-cooled compute module in orbit.

    Usage:
        cfg = ThermalConfig(tdp_watts=5.0)
        model = OrbitalThermalModel(cfg)
        states = model.simulate(n_orbits=3, dt_s=10.0)
    """

    def __init__(self, cfg: ThermalConfig):
        self.cfg = cfg
        self.orbital = OrbitalParameters.for_altitude(cfg.altitude)

    def simulate(
        self,
        n_orbits: float = 2.0,
        dt_s: float = 10.0,
        compute_active: bool = True,
    ) -> list[ThermalState]:
        total_s = n_orbits * self.orbital.period_s
        t = 0.0
        temp_k = self.cfg.t_op_min_c + 273.15 + 20   # start 20°C above min

        states = []

        while t < total_s:
            in_eclipse = self._in_eclipse(t)
            p_in = self._power_in(in_eclipse)
            p_compute = self.cfg.tdp_watts if compute_active else self.cfg.idle_watts

            throttle = self._throttle(temp_k - 273.15)
            p_actual_compute = p_compute * throttle

            p_out = self._power_out(temp_k)

            dT_dt = (p_in + p_actual_compute - p_out) / self.cfg.thermal_mass_j_per_k
            temp_k = max(temp_k + dT_dt * dt_s, 1.0)   # physical floor

            state = ThermalState(
                t_seconds=t,
                temp_c=temp_k - 273.15,
                temp_k=temp_k,
                p_in_w=p_in,
                p_out_w=p_out,
                p_compute_w=p_actual_compute,
                in_eclipse=in_eclipse,
                throttle_factor=throttle,
                in_safe_range=(self.cfg.t_op_min_c <= temp_k - 273.15 <= self.cfg.t_op_max_c),
            )
            states.append(state)
            t += dt_s

        return states

    def steady_state_temp(self, compute_watts: float, in_eclipse: bool = False) -> float:
        """Estimate equilibrium temperature in Kelvin."""
        p_in = self._power_in(in_eclipse)
        # Solve: p_in + p_compute = epsilon * sigma * A * T^4
        total_in = p_in + compute_watts
        g = self.cfg.geometry
        A = g.radiator_area_m2
        eps = g.epsilon_radiator
        T4 = total_in / max(eps * STEFAN_BOLTZMANN * A, 1e-20)
        return T4 ** 0.25

    def radiator_area_required(self, compute_watts: float, t_max_k: float) -> float:
        """Minimum radiator area (m²) to stay below t_max_k."""
        p_in = self._power_in(in_eclipse=False)   # worst case: full sun
        total_in = p_in + compute_watts
        g = self.cfg.geometry
        eps = g.epsilon_radiator
        return total_in / (eps * STEFAN_BOLTZMANN * t_max_k**4)

    def _in_eclipse(self, t: float) -> bool:
        phase = (t % self.orbital.period_s) / self.orbital.period_s
        return phase > (1.0 - self.orbital.eclipse_fraction)

    def _power_in(self, in_eclipse: bool) -> float:
        g = self.cfg.geometry
        if in_eclipse:
            # Only Earth IR, no solar
            p_earth_ir = EARTH_IR_FLUX * g.cross_section_m2 * g.epsilon_body
            return p_earth_ir
        else:
            # Solar direct + albedo + Earth IR
            p_solar = SOLAR_FLUX_LEO * g.solar_alpha * g.cross_section_m2
            p_albedo = SOLAR_FLUX_LEO * EARTH_ALBEDO * g.solar_alpha * g.cross_section_m2 * 0.5
            p_earth_ir = EARTH_IR_FLUX * g.cross_section_m2 * g.epsilon_body
            return p_solar + p_albedo + p_earth_ir

    def _power_out(self, temp_k: float) -> float:
        g = self.cfg.geometry
        # Radiator face (high emissivity)
        p_rad = g.epsilon_radiator * STEFAN_BOLTZMANN * g.radiator_area_m2 * temp_k**4
        # Other faces (low emissivity polished Al)
        other_area = g.total_surface_m2 - g.radiator_area_m2
        p_body = g.epsilon_body * STEFAN_BOLTZMANN * other_area * temp_k**4
        return p_rad + p_body

    def _throttle(self, temp_c: float) -> float:
        if temp_c < self.cfg.t_throttle_c:
            return 1.0
        if temp_c >= self.cfg.t_op_max_c:
            return 0.0
        span = self.cfg.t_op_max_c - self.cfg.t_throttle_c
        return 1.0 - (temp_c - self.cfg.t_throttle_c) / span


def thermal_summary(states: list[ThermalState]) -> dict:
    temps = [s.temp_c for s in states]
    throttle = [s.throttle_factor for s in states]
    unsafe = [s for s in states if not s.in_safe_range]
    eclipse = [s for s in states if s.in_eclipse]

    return {
        "t_min_c": min(temps),
        "t_max_c": max(temps),
        "t_mean_c": sum(temps) / len(temps),
        "throttle_min": min(throttle),
        "throttle_mean": sum(throttle) / len(throttle),
        "unsafe_fraction": len(unsafe) / len(states),
        "eclipse_fraction": len(eclipse) / len(states),
        "total_sim_s": states[-1].t_seconds,
    }
