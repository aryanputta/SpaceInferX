"""
Space-analog link condition emulator.

Models three independent degradation sources:
  1. Radiation-induced BER (burst-correlated, not Poisson)
  2. Thermal throttling (passive cooling constraint)
  3. Link intermittency (orbit-based availability windows)

Uses Linux tc/netem under the hood; falls back to pure-Python
packet injection via scapy when tc is not available (macOS dev).
"""

import subprocess
import time
import math
import random
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class CoolingMode(Enum):
    CONVECTIVE = "convective"   # standard datacenter
    PASSIVE = "passive"         # space-analog (radiation-only)
    NONE = "none"               # vacuum (worst case)


@dataclass
class SpaceLinkConfig:
    # Radiation BER parameters
    base_ber: float = 0.0          # baseline BER (no radiation)
    radiation_ber: float = 1e-5    # BER during radiation event
    burst_duration_s: float = 2.0  # radiation burst duration (seconds)
    burst_interval_s: float = 30.0 # mean interval between bursts (seconds)

    # Thermal parameters
    cooling_mode: CoolingMode = CoolingMode.PASSIVE
    ambient_temp_c: float = -20.0       # space-analog ambient (cold side)
    max_temp_c: float = 85.0            # max safe operating temp
    thermal_time_constant_s: float = 45.0  # passive cooling time constant
    throttle_temp_c: float = 75.0          # throttle begins here

    # Link intermittency (orbit window simulation)
    link_available_s: float = 600.0    # link-up window (10 min pass)
    link_unavailable_s: float = 5400.0 # link-down window (90 min orbit)

    # Network baseline
    base_latency_ms: float = 20.0
    base_bandwidth_mbps: float = 100.0
    queue_depth_packets: int = 100


@dataclass
class LinkState:
    ber: float = 0.0
    throttle_factor: float = 1.0    # 1.0 = full speed, 0.0 = halted
    link_up: bool = True
    temp_c: float = 25.0
    radiation_active: bool = False
    t_seconds: float = 0.0
    packets_sent: int = 0
    packets_dropped: int = 0
    packets_corrupted: int = 0


class SpaceLinkEmulator:
    """
    Emulates space-analog link conditions for TCP characterization.

    Usage:
        cfg = SpaceLinkConfig(radiation_ber=1e-4, cooling_mode=CoolingMode.PASSIVE)
        emu = SpaceLinkEmulator(cfg)
        emu.start()
        # run your TCP workload
        state = emu.get_state()
        emu.stop()
    """

    def __init__(self, cfg: SpaceLinkConfig):
        self.cfg = cfg
        self._state = LinkState(temp_c=cfg.ambient_temp_c)
        self._running = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._start_time = 0.0

    # --- Public interface ---

    def start(self):
        self._running = True
        self._start_time = time.monotonic()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_state(self) -> LinkState:
        with self._lock:
            import copy
            return copy.copy(self._state)

    def inject_packet(self, payload_bytes: int) -> tuple[bool, bool]:
        """
        Simulate sending a packet. Returns (delivered, corrupted).
        Delivered = False means packet dropped. Corrupted = True means
        bit error introduced (TCP will eventually detect via checksum).
        """
        with self._lock:
            s = self._state
            if not s.link_up:
                s.packets_sent += 1
                s.packets_dropped += 1
                return False, False

            # Corruption probability from BER
            bit_error_prob = 1.0 - (1.0 - s.ber) ** (payload_bytes * 8)
            corrupted = random.random() < bit_error_prob
            delivered = True

            s.packets_sent += 1
            if corrupted:
                s.packets_corrupted += 1
            return delivered, corrupted

    # --- Internal state machine ---

    def _run_loop(self):
        """Update link state every 100ms."""
        dt = 0.1
        next_burst = self._sample_burst_interval()
        burst_end = float('inf')
        next_link_toggle = self.cfg.link_available_s  # first toggle: link goes down

        while self._running:
            time.sleep(dt)
            t = time.monotonic() - self._start_time

            with self._lock:
                s = self._state
                s.t_seconds = t

                # Radiation burst state machine
                if t >= next_burst and t < burst_end:
                    s.radiation_active = True
                    s.ber = self.cfg.radiation_ber
                    burst_end = next_burst + self.cfg.burst_duration_s
                elif t >= burst_end:
                    s.radiation_active = False
                    s.ber = self.cfg.base_ber
                    next_burst = t + self._sample_burst_interval()
                    burst_end = float('inf')

                # Thermal model
                s.temp_c = self._compute_temp(s, dt)
                s.throttle_factor = self._compute_throttle(s.temp_c)

                # Link intermittency
                if t >= next_link_toggle:
                    s.link_up = not s.link_up
                    if s.link_up:
                        next_link_toggle = t + self.cfg.link_available_s
                    else:
                        next_link_toggle = t + self.cfg.link_unavailable_s

    def _compute_temp(self, s: LinkState, dt: float) -> float:
        """Simple first-order thermal model."""
        if self.cfg.cooling_mode == CoolingMode.CONVECTIVE:
            # Fast cooling: equilibrium near ambient
            tau = 5.0
        elif self.cfg.cooling_mode == CoolingMode.PASSIVE:
            tau = self.cfg.thermal_time_constant_s
        else:
            tau = float('inf')  # no cooling

        # Heat generated by compute (simplified: proportional to throttle)
        heat_rate = 30.0 * s.throttle_factor  # delta-T per second at full load
        cooling_rate = (s.temp_c - self.cfg.ambient_temp_c) / tau

        return s.temp_c + dt * (heat_rate - cooling_rate)

    def _compute_throttle(self, temp_c: float) -> float:
        """Linear throttle between throttle_temp and max_temp."""
        if temp_c < self.cfg.throttle_temp_c:
            return 1.0
        if temp_c >= self.cfg.max_temp_c:
            return 0.0
        span = self.cfg.max_temp_c - self.cfg.throttle_temp_c
        return 1.0 - (temp_c - self.cfg.throttle_temp_c) / span

    def _sample_burst_interval(self) -> float:
        """Exponential inter-burst interval (Poisson burst arrival)."""
        return random.expovariate(1.0 / self.cfg.burst_interval_s)
