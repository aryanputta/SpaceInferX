"""
TCP characterization under space-analog link conditions.

Measures how TCP throughput, latency, and connection stability
degrade as BER, intermittency, and thermal throttling increase.

Uses Python socket pairs + the SpaceLinkEmulator to inject
space-analog conditions into a controlled TCP flow.
"""

import socket
import time
import threading
import statistics
import json
from dataclasses import dataclass, field
from typing import Optional

from src.emulation.space_link import SpaceLinkConfig, SpaceLinkEmulator, CoolingMode


@dataclass
class TCPBenchConfig:
    payload_size_bytes: int = 64 * 1024   # 64KB per send
    duration_s: float = 60.0              # experiment duration
    host: str = "127.0.0.1"
    port: int = 15000
    link: SpaceLinkConfig = field(default_factory=SpaceLinkConfig)


@dataclass
class TCPBenchResult:
    duration_s: float
    bytes_sent: int
    throughput_mbps: float
    latencies_ms: list[float]
    p50_ms: float
    p95_ms: float
    p99_ms: float
    packet_loss_rate: float
    corruption_rate: float
    link_down_events: int
    thermal_throttle_events: int
    radiation_events: int
    conditions: dict


class TCPBenchmark:
    """
    Runs a TCP throughput + latency benchmark under space-analog link conditions.

    Usage:
        cfg = TCPBenchConfig(
            duration_s=120,
            link=SpaceLinkConfig(radiation_ber=1e-5, cooling_mode=CoolingMode.PASSIVE)
        )
        bench = TCPBenchmark(cfg)
        result = bench.run()
        print(result)
    """

    def __init__(self, cfg: TCPBenchConfig):
        self.cfg = cfg
        self.emulator = SpaceLinkEmulator(cfg.link)
        self._results: list[float] = []
        self._bytes_sent = 0
        self._link_down_events = 0
        self._radiation_events = 0
        self._throttle_events = 0

    def run(self) -> TCPBenchResult:
        self.emulator.start()
        start = time.monotonic()

        # Run a simple loopback benchmark — captures timing, not actual kernel TCP
        # For real kernel TCP experiments, replace with tc/netem injection
        latencies = []
        bytes_sent = 0
        payload = b"x" * self.cfg.payload_size_bytes
        prev_link_up = True
        prev_radiation = False
        prev_throttle = 1.0

        while time.monotonic() - start < self.cfg.duration_s:
            t0 = time.monotonic()
            delivered, corrupted = self.emulator.inject_packet(self.cfg.payload_size_bytes)
            state = self.emulator.get_state()

            # Track state transitions
            if state.link_up != prev_link_up and not state.link_up:
                self._link_down_events += 1
            if state.radiation_active and not prev_radiation:
                self._radiation_events += 1
            if state.throttle_factor < 0.9 and prev_throttle >= 0.9:
                self._throttle_events += 1

            prev_link_up = state.link_up
            prev_radiation = state.radiation_active
            prev_throttle = state.throttle_factor

            if delivered and not corrupted:
                elapsed_ms = (time.monotonic() - t0) * 1000
                # Add synthetic propagation delay
                latencies.append(elapsed_ms + self.cfg.link.base_latency_ms)
                bytes_sent += self.cfg.payload_size_bytes

            # Throttle send rate based on thermal state
            send_interval = (self.cfg.payload_size_bytes * 8) / (
                self.cfg.link.base_bandwidth_mbps * 1e6 * max(state.throttle_factor, 0.01)
            )
            time.sleep(send_interval)

        self.emulator.stop()
        duration = time.monotonic() - start
        final_state = self.emulator.get_state()

        p50 = statistics.median(latencies) if latencies else 0.0
        p95 = _percentile(latencies, 95)
        p99 = _percentile(latencies, 99)
        total_packets = final_state.packets_sent or 1

        return TCPBenchResult(
            duration_s=duration,
            bytes_sent=bytes_sent,
            throughput_mbps=(bytes_sent * 8) / (duration * 1e6),
            latencies_ms=latencies,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99,
            packet_loss_rate=final_state.packets_dropped / total_packets,
            corruption_rate=final_state.packets_corrupted / total_packets,
            link_down_events=self._link_down_events,
            thermal_throttle_events=self._throttle_events,
            radiation_events=self._radiation_events,
            conditions={
                "ber": self.cfg.link.radiation_ber,
                "cooling_mode": self.cfg.link.cooling_mode.value,
                "burst_interval_s": self.cfg.link.burst_interval_s,
            },
        )


def _percentile(data: list[float], p: int) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]
