"""
TCP BER sweep experiment.

Sweeps radiation BER from 0 to 1e-3 and measures how TCP metrics
degrade. Produces a results JSON for plotting.

Run:
    python3 experiments/tcp_characterization/run_sweep.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.emulation.space_link import SpaceLinkConfig, CoolingMode
from src.networking.tcp_bench import TCPBenchmark, TCPBenchConfig

BER_SWEEP = [0, 1e-7, 1e-6, 1e-5, 5e-5, 1e-4, 5e-4, 1e-3]
DURATION_S = 30.0   # per condition
OUTPUT_FILE = "results/space_analog/tcp_ber_sweep.json"


def main():
    os.makedirs("results/space_analog", exist_ok=True)
    results = []

    for ber in BER_SWEEP:
        print(f"[sweep] BER={ber:.0e} ...", flush=True)
        link_cfg = SpaceLinkConfig(
            base_ber=0.0,
            radiation_ber=ber,
            burst_interval_s=10.0,
            burst_duration_s=2.0,
            cooling_mode=CoolingMode.PASSIVE,
        )
        bench_cfg = TCPBenchConfig(duration_s=DURATION_S, link=link_cfg)
        bench = TCPBenchmark(bench_cfg)
        r = bench.run()
        entry = {
            "ber": ber,
            "throughput_mbps": r.throughput_mbps,
            "p50_ms": r.p50_ms,
            "p95_ms": r.p95_ms,
            "p99_ms": r.p99_ms,
            "packet_loss_rate": r.packet_loss_rate,
            "corruption_rate": r.corruption_rate,
            "link_down_events": r.link_down_events,
            "radiation_events": r.radiation_events,
        }
        results.append(entry)
        print(f"  throughput={r.throughput_mbps:.2f} Mbps  "
              f"p50={r.p50_ms:.1f}ms  loss={r.packet_loss_rate:.4f}")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
