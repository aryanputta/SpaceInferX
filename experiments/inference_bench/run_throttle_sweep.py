"""
Inference throughput sweep across thermal throttle levels.

Simulates space-analog thermal throttling by reducing effective CPU thread
count. Measures tokens/sec, TTFT, and latency across throttle levels from
1.0 (full speed) down to 0.1 (10% — near-thermal-shutdown).

Run:
    python3 experiments/inference_bench/run_throttle_sweep.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.inference.llama_bench import LlamaBench, InferenceBenchConfig

THROTTLE_LEVELS = [1.0, 0.9, 0.75, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
OUTPUT_FILE = "results/space_analog/inference_throttle_sweep.json"
N_PREDICT = 128


def main():
    os.makedirs("results/space_analog", exist_ok=True)
    results = []

    print(f"Running inference benchmark across {len(THROTTLE_LEVELS)} throttle levels")
    print(f"Model: TinyLlama-1.1B Q4_K_M  |  Tokens to generate: {N_PREDICT}\n")

    for throttle in THROTTLE_LEVELS:
        print(f"[throttle={throttle:.1f}] running...", flush=True)
        cfg = InferenceBenchConfig(throttle_factor=throttle, n_predict=N_PREDICT)
        bench = LlamaBench(cfg)
        r = bench.run()

        entry = {
            "throttle_factor": throttle,
            "pp_tokens_per_sec": r.pp_tokens_per_sec,
            "tg_tokens_per_sec": r.tg_tokens_per_sec,
            "ttft_ms": r.ttft_ms,
            "total_latency_ms": r.total_latency_ms,
            "tokens_generated": r.tokens_generated,
        }
        results.append(entry)

        print(f"  pp={r.pp_tokens_per_sec:.1f} t/s  "
              f"tg={r.tg_tokens_per_sec:.1f} t/s  "
              f"ttft={r.ttft_ms:.0f}ms  "
              f"total={r.total_latency_ms/1000:.1f}s")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
