"""
macOS dummynet-based kernel TCP emulator.

Uses dnctl + pfctl to inject real OS-level packet loss, delay, and
bandwidth constraints — capturing actual TCP congestion control behavior
(retransmit timers, window scaling, SACK) rather than simulated drops.

Requires sudo for pfctl/dnctl operations. Run experiments with:
    sudo python3 experiments/tcp_characterization/run_kernel_sweep.py

BER → PLR mapping:
    For 64KB payload (524288 bits), P(at least one error) = 1-(1-BER)^524288
    We use per-packet PLR derived from BER and payload size.
"""

import subprocess
import shlex
import time
import math
from dataclasses import dataclass
from contextlib import contextmanager


PIPE_NUM = 42          # dummynet pipe number (arbitrary, avoid collisions)
ANCHOR = "spaceinferx" # pf anchor name


def _run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(shlex.split(cmd), capture_output=True, text=True, check=check)


def ber_to_plr(ber: float, payload_bytes: int = 65536) -> float:
    """Convert BER to per-packet loss rate for given payload size."""
    if ber == 0.0:
        return 0.0
    n_bits = payload_bytes * 8
    return 1.0 - (1.0 - ber) ** n_bits


@dataclass
class DummynetConfig:
    bandwidth_mbps: float = 100.0
    delay_ms: float = 20.0
    plr: float = 0.0            # packet loss rate [0, 1]
    burst_ms: float = 0.0       # burst loss window in ms (0 = no burst)
    queue_slots: int = 100
    port: int = 15001           # target port to shape


class DummynetEmulator:
    """
    Wraps dnctl + pfctl to apply space-analog link conditions at kernel level.

    Usage:
        cfg = DummynetConfig(plr=0.05, delay_ms=20, bandwidth_mbps=50)
        with DummynetEmulator(cfg) as emu:
            # run iperf3 or your TCP workload here
            pass
    """

    def __init__(self, cfg: DummynetConfig):
        self.cfg = cfg

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    def start(self):
        self._setup_pipe()
        self._setup_pf()

    def stop(self):
        self._teardown_pf()
        self._teardown_pipe()

    def _setup_pipe(self):
        bw = f"{self.cfg.bandwidth_mbps:.0f}Mbit/s"
        delay = f"{self.cfg.delay_ms:.0f}ms"
        plr = f"{self.cfg.plr:.6f}"
        cmd = (
            f"dnctl pipe {PIPE_NUM} config "
            f"bw {bw} delay {delay} plr {plr} "
            f"queue {self.cfg.queue_slots}slots"
        )
        _run(cmd)

    def _setup_pf(self):
        rules = (
            f'anchor "{ANCHOR}"\n'
        )
        anchor_rules = (
            f'dummynet out proto tcp to any port {self.cfg.port} pipe {PIPE_NUM}\n'
            f'dummynet in proto tcp from any port {self.cfg.port} pipe {PIPE_NUM}\n'
        )
        # Load anchor rules
        proc = subprocess.run(
            ["pfctl", "-a", ANCHOR, "-f", "-"],
            input=anchor_rules, text=True, capture_output=True
        )
        # Enable pf if not already (ignore error if already enabled)
        subprocess.run(["pfctl", "-e"], capture_output=True)

    def _teardown_pf(self):
        subprocess.run(["pfctl", "-a", ANCHOR, "-F", "all"], capture_output=True)

    def _teardown_pipe(self):
        subprocess.run(shlex.split(f"dnctl pipe {PIPE_NUM} delete"), capture_output=True)

    def get_pipe_stats(self) -> dict:
        """Read dummynet pipe statistics."""
        result = _run(f"dnctl pipe {PIPE_NUM} show", check=False)
        return {"raw": result.stdout.strip()}
