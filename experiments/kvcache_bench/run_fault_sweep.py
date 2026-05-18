"""
KV cache fault injection sweep.

Sweeps BER from 0 to 1e-3 across three fault modes (SEU, MUU, page-level)
and measures attention output degradation. Produces results JSON.

Run:
    python3 experiments/kvcache_bench/run_fault_sweep.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import numpy as np
from src.kvcache.fault_model import (
    KVCacheFaultInjector, FaultConfig,
    measure_output_degradation, scaled_dot_product_attention,
)

BER_SWEEP = [0, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3]
FAULT_MODES = ["seu", "muu", "page"]
SEQ_LEN = 512
HEAD_DIM = 64
N_HEADS = 8
OUTPUT_FILE = "results/space_analog/kvcache_fault_sweep.json"


def main():
    os.makedirs("results/space_analog", exist_ok=True)
    results = []

    # Reference KV cache (numpy, float32)
    rng = np.random.default_rng(0)
    k_ref = rng.standard_normal((1, N_HEADS, SEQ_LEN, HEAD_DIM)).astype(np.float32)
    v_ref = rng.standard_normal((1, N_HEADS, SEQ_LEN, HEAD_DIM)).astype(np.float32)
    q = rng.standard_normal((1, N_HEADS, 1, HEAD_DIM)).astype(np.float32)
    out_ref = scaled_dot_product_attention(q, k_ref, v_ref)

    for mode in FAULT_MODES:
        for ber in BER_SWEEP:
            print(f"[sweep] mode={mode}  BER={ber:.0e} ...", flush=True)
            cfg = FaultConfig(ber=ber, mode=mode)
            injector = KVCacheFaultInjector(cfg)

            # Average over 10 trials
            trial_metrics = []
            for trial in range(10):
                cfg.seed = trial
                injector = KVCacheFaultInjector(cfg)
                k_fault, v_fault = injector.inject(k_ref.copy(), v_ref.copy())
                out_fault = scaled_dot_product_attention(q, k_fault, v_fault)
                metrics = measure_output_degradation(out_ref, out_fault)
                trial_metrics.append(metrics)

            avg = {
                k: sum(m[k] for m in trial_metrics) / len(trial_metrics)
                if isinstance(trial_metrics[0][k], float)
                else trial_metrics[-1][k]
                for k in trial_metrics[0]
            }
            results.append({"mode": mode, "ber": ber, **avg})
            print(f"  cosine_sim={avg['cosine_similarity']:.6f}  "
                  f"mse={avg['mse']:.2e}")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
