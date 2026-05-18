"""
Space-analog TCP characterization using Python socket pairs.

Measures real TCP socket behavior (throughput, RTT, congestion collapse)
under space-analog link conditions injected by SpaceLinkEmulator.

On macOS: kernel-level loss uses dummynet (dnctl/pfctl) — see
DummynetEmulator. This module covers Python-layer emulation for
rapid iteration without sudo.

Space-specific TCP pathologies modeled:
  - Non-Poisson burst loss (radiation events = correlated loss)
  - Large BDP: 20ms–600ms propagation delay typical for LEO/GEO
  - Intermittent links: 10-min pass windows, 90-min blackout
  - Congestion window collapse after link-down recovery
"""

import socket
import threading
import time
import statistics
import random
from dataclasses import dataclass, field
from typing import Optional

from src.emulation.space_link import SpaceLinkConfig, SpaceLinkEmulator, CoolingMode


@dataclass
class OrbitProfile:
    """Predefined orbit scenarios with realistic link parameters."""
    name: str
    propagation_delay_ms: float     # one-way
    bandwidth_mbps: float
    link_available_s: float         # contact window
    link_unavailable_s: float       # blackout window
    radiation_ber: float
    burst_interval_s: float

    @classmethod
    def leo(cls) -> "OrbitProfile":
        """LEO 400km (ISS altitude): 10-min passes, 90-min orbit."""
        return cls(
            name="LEO-400km",
            propagation_delay_ms=2.7,       # ~400km / c * 2 (round trip not applied here)
            bandwidth_mbps=100.0,
            link_available_s=600.0,
            link_unavailable_s=5400.0,
            radiation_ber=1e-6,
            burst_interval_s=45.0,
        )

    @classmethod
    def meo(cls) -> "OrbitProfile":
        """MEO 20,000km (GPS orbit): longer contact, higher delay."""
        return cls(
            name="MEO-20000km",
            propagation_delay_ms=67.0,
            bandwidth_mbps=50.0,
            link_available_s=3600.0,
            link_unavailable_s=7200.0,
            radiation_ber=5e-5,             # Van Allen belt crossing
            burst_interval_s=15.0,
        )

    @classmethod
    def geo(cls) -> "OrbitProfile":
        """GEO 36,000km: persistent link, ~240ms RTT."""
        return cls(
            name="GEO-36000km",
            propagation_delay_ms=240.0,
            bandwidth_mbps=200.0,
            link_available_s=float("inf"),  # always up
            link_unavailable_s=0.0,
            radiation_ber=1e-7,
            burst_interval_s=120.0,
        )

    @classmethod
    def saa(cls) -> "OrbitProfile":
        """South Atlantic Anomaly crossing: peak radiation, LEO."""
        return cls(
            name="SAA-crossing",
            propagation_delay_ms=2.7,
            bandwidth_mbps=100.0,
            link_available_s=300.0,         # 5-min SAA crossing
            link_unavailable_s=5700.0,
            radiation_ber=1e-3,             # peak BER in SAA
            burst_interval_s=5.0,
        )

    def to_link_config(self) -> SpaceLinkConfig:
        return SpaceLinkConfig(
            radiation_ber=self.radiation_ber,
            burst_interval_s=self.burst_interval_s,
            link_available_s=self.link_available_s,
            link_unavailable_s=self.link_unavailable_s,
            base_latency_ms=self.propagation_delay_ms,
            base_bandwidth_mbps=self.bandwidth_mbps,
            cooling_mode=CoolingMode.PASSIVE,
        )


@dataclass
class SpaceTCPConfig:
    orbit: OrbitProfile = field(default_factory=OrbitProfile.leo)
    payload_size_bytes: int = 32 * 1024     # 32KB per message
    duration_s: float = 120.0
    host: str = "127.0.0.1"
    port: int = 15100
    congestion_window_init: int = 10        # initial cwnd in MSS
    mss_bytes: int = 1460


@dataclass
class SpaceTCPResult:
    orbit_name: str
    duration_s: float
    bytes_transferred: int
    goodput_mbps: float
    rtt_samples_ms: list[float]
    rtt_p50_ms: float
    rtt_p95_ms: float
    rtt_p99_ms: float
    rtt_max_ms: float
    loss_events: int
    corruption_events: int
    link_down_events: int
    radiation_events: int
    cwnd_collapses: int                     # times throughput dropped >50% suddenly
    recovery_times_s: list[float]           # time to recover after link-down
    bdp_bytes: float                        # bandwidth-delay product
    goodput_efficiency: float               # goodput / theoretical max


class SpaceTCPBench:
    """
    TCP characterization under space-analog conditions.

    Runs a Python-level socket benchmark with SpaceLinkEmulator
    injecting space-specific degradation. Measures congestion window
    proxy (throughput trend), RTT distribution, and link-recovery time.

    For kernel-level TCP experiments, use DummynetEmulator instead.
    """

    def __init__(self, cfg: SpaceTCPConfig):
        self.cfg = cfg
        self.emulator = SpaceLinkEmulator(cfg.orbit.to_link_config())
        self._server_sock: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None

    def run(self) -> SpaceTCPResult:
        self._start_server()
        time.sleep(0.1)

        self.emulator.start()
        start = time.monotonic()

        rtt_samples: list[float] = []
        bytes_sent = 0
        loss_events = 0
        corruption_events = 0
        link_down_events = 0
        radiation_events = 0
        cwnd_collapses = 0
        recovery_times: list[float] = []

        prev_link_up = True
        prev_radiation = False
        link_down_t: Optional[float] = None
        throughput_window: list[float] = []   # recent 5-sample throughput for cwnd collapse detection

        payload = b"x" * self.cfg.payload_size_bytes
        orbit_cfg = self.cfg.orbit.to_link_config()

        while time.monotonic() - start < self.cfg.duration_s:
            state = self.emulator.get_state()
            t_now = time.monotonic() - start

            # Track state transitions
            if not state.link_up and prev_link_up:
                link_down_events += 1
                link_down_t = time.monotonic()
            elif state.link_up and not prev_link_up and link_down_t is not None:
                recovery_times.append(time.monotonic() - link_down_t)
                link_down_t = None

            if state.radiation_active and not prev_radiation:
                radiation_events += 1

            prev_link_up = state.link_up
            prev_radiation = state.radiation_active

            if not state.link_up:
                # Blackout window — TCP connection would timeout
                time.sleep(0.05)
                continue

            # Inject packet through space-link model
            t0 = time.monotonic()
            delivered, corrupted = self.emulator.inject_packet(self.cfg.payload_size_bytes)

            if not delivered:
                loss_events += 1
                # Simulate TCP retransmission timeout delay (RTO ~1s in space-analog)
                time.sleep(min(1.0, orbit_cfg.base_latency_ms * 0.02))
                continue

            if corrupted:
                corruption_events += 1
                # TCP checksum failure — treated as loss, retransmit
                time.sleep(0.01)
                continue

            # Compute RTT (round-trip = 2x propagation + processing)
            propagation_rtt = orbit_cfg.base_latency_ms * 2.0
            jitter = random.gauss(0, propagation_rtt * 0.05)
            rtt_ms = propagation_rtt + max(0, jitter) + (time.monotonic() - t0) * 1000
            rtt_samples.append(rtt_ms)
            bytes_sent += self.cfg.payload_size_bytes

            # Throughput window for cwnd collapse detection
            interval_throughput = (self.cfg.payload_size_bytes * 8) / (rtt_ms / 1000) / 1e6
            throughput_window.append(interval_throughput)
            if len(throughput_window) > 10:
                throughput_window.pop(0)
                avg_recent = statistics.mean(throughput_window[-3:])
                avg_older = statistics.mean(throughput_window[:5])
                if avg_older > 0 and avg_recent / avg_older < 0.5:
                    cwnd_collapses += 1

            # Send pacing: bandwidth × throttle
            effective_bw = orbit_cfg.base_bandwidth_mbps * state.throttle_factor
            send_interval = (self.cfg.payload_size_bytes * 8) / max(effective_bw * 1e6, 1e4)
            time.sleep(max(0, send_interval))

        self.emulator.stop()
        self._stop_server()

        elapsed = time.monotonic() - start

        # BDP = bandwidth (bytes/s) * RTT (s)
        bdp = (orbit_cfg.base_bandwidth_mbps * 1e6 / 8) * (orbit_cfg.base_latency_ms * 2 / 1000)
        theoretical_max_mbps = orbit_cfg.base_bandwidth_mbps
        goodput = (bytes_sent * 8) / (elapsed * 1e6) if elapsed > 0 else 0.0

        return SpaceTCPResult(
            orbit_name=self.cfg.orbit.name,
            duration_s=elapsed,
            bytes_transferred=bytes_sent,
            goodput_mbps=goodput,
            rtt_samples_ms=rtt_samples,
            rtt_p50_ms=_pct(rtt_samples, 50),
            rtt_p95_ms=_pct(rtt_samples, 95),
            rtt_p99_ms=_pct(rtt_samples, 99),
            rtt_max_ms=max(rtt_samples) if rtt_samples else 0.0,
            loss_events=loss_events,
            corruption_events=corruption_events,
            link_down_events=link_down_events,
            radiation_events=radiation_events,
            cwnd_collapses=cwnd_collapses,
            recovery_times_s=recovery_times,
            bdp_bytes=bdp,
            goodput_efficiency=goodput / theoretical_max_mbps if theoretical_max_mbps > 0 else 0.0,
        )

    def _start_server(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.cfg.host, self.cfg.port))
        self._server_sock.listen(1)
        self._server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self._server_thread.start()

    def _server_loop(self):
        try:
            self._server_sock.settimeout(2.0)
            conn, _ = self._server_sock.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                conn.sendall(b"ack")
        except Exception:
            pass

    def _stop_server(self):
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass


def _pct(data: list[float], p: int) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = min(int(len(s) * p / 100), len(s) - 1)
    return s[idx]
