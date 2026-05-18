"""
TCP characterization across orbit scenarios.

Sweeps all four orbital profiles (LEO-400, MEO, GEO, SAA crossing)
and measures TCP goodput, RTT, loss, and congestion collapse behavior.
Results quantify how orbit choice affects inference data pipeline performance.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.networking.space_tcp import SpaceTCPBench, SpaceTCPConfig, OrbitProfile

RESULTS_DIR = Path("results/space_analog")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ORBITS = [
    OrbitProfile.leo(),
    OrbitProfile.meo(),
    OrbitProfile.geo(),
    OrbitProfile.saa(),
]

DURATION_S = 60.0   # 60s per orbit scenario


def run_orbit(orbit: OrbitProfile) -> dict:
    cfg = SpaceTCPConfig(
        orbit=orbit,
        payload_size_bytes=32 * 1024,
        duration_s=DURATION_S,
        port=15100 + ORBITS.index(orbit),
    )
    bench = SpaceTCPBench(cfg)
    print(f"  Running {orbit.name} (BER={orbit.radiation_ber:.0e}, delay={orbit.propagation_delay_ms:.0f}ms)...")
    t0 = time.time()
    r = bench.run()
    elapsed = time.time() - t0

    return {
        "orbit": r.orbit_name,
        "radiation_ber": orbit.radiation_ber,
        "propagation_delay_ms": orbit.propagation_delay_ms,
        "bandwidth_mbps": orbit.bandwidth_mbps,
        "duration_s": r.duration_s,
        "goodput_mbps": round(r.goodput_mbps, 4),
        "goodput_efficiency": round(r.goodput_efficiency, 4),
        "rtt_p50_ms": round(r.rtt_p50_ms, 2),
        "rtt_p95_ms": round(r.rtt_p95_ms, 2),
        "rtt_p99_ms": round(r.rtt_p99_ms, 2),
        "rtt_max_ms": round(r.rtt_max_ms, 2),
        "loss_events": r.loss_events,
        "corruption_events": r.corruption_events,
        "link_down_events": r.link_down_events,
        "radiation_events": r.radiation_events,
        "cwnd_collapses": r.cwnd_collapses,
        "recovery_times_s": r.recovery_times_s,
        "avg_recovery_s": (sum(r.recovery_times_s) / len(r.recovery_times_s)) if r.recovery_times_s else 0.0,
        "bdp_bytes": round(r.bdp_bytes, 0),
    }


def main():
    print("TCP Orbit Sweep — SpaceInferX Track 1")
    print("=" * 50)
    results = []
    for orbit in ORBITS:
        result = run_orbit(orbit)
        results.append(result)
        print(f"  {result['orbit']}: goodput={result['goodput_mbps']:.2f} Mbps, "
              f"RTT p50={result['rtt_p50_ms']:.1f}ms, "
              f"loss={result['loss_events']}, collapses={result['cwnd_collapses']}")

    out = RESULTS_DIR / "tcp_orbit_sweep.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {out}")

    # Print summary table
    print("\nSummary:")
    print(f"{'Orbit':<20} {'Goodput':>10} {'Efficiency':>12} {'RTT p50':>10} {'Loss':>8} {'CWND Collapses':>16}")
    print("-" * 80)
    for r in results:
        print(f"{r['orbit']:<20} {r['goodput_mbps']:>9.2f}M {r['goodput_efficiency']:>11.1%} "
              f"{r['rtt_p50_ms']:>9.1f}ms {r['loss_events']:>7} {r['cwnd_collapses']:>15}")


if __name__ == "__main__":
    main()
