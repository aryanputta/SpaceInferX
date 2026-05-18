# SpaceInferX

**Space-Analog AI Inference Characterization**

Research project studying LLM inference and KV cache behavior under space-like operating conditions.

## Research Question

How do LLM inference metrics — throughput, latency, KV cache hit rate, output correctness — degrade when compute operates under space-analog constraints: radiation-elevated BER, passive thermal management only, and intermittent network links?

## Funding

$5,000 research grant — TCP networking and space-analog compute study.

## Two Tracks

### Track 1 — Networking (Software, active)
Characterize TCP behavior under space-analog link conditions using Python-based link emulation. Uses tc/netem for link degradation modeling.

### Track 2 — Hardware (Design phase)
Modular compute unit with passive cooling, radiation-component selection, thermal interface design. Physical platform for Track 1 experiments.

## Project Structure

```
src/
  emulation/      # Space-analog link and hardware condition emulation
  inference/      # LLM inference benchmarking (vLLM, MLC-LLM)
  kvcache/        # KV cache behavior under fault conditions
  networking/     # TCP characterization under degraded links
  thermal/        # Thermal simulation and throttling models
experiments/
  tcp_characterization/   # TCP failure modes under space-analog links
  inference_bench/        # Inference throughput/latency under faults
  kvcache_bench/          # KV cache hit rate, eviction, corruption
  thermal_sim/            # Passive cooling thermal dynamics
results/
  baseline/       # Standard datacenter conditions
  space_analog/   # Space-like conditions
  degraded/       # Intermediate degradation levels
```

## Key Papers (from advisors and collaborators)

| Paper | Relevance |
|---|---|
| PagedAttention (Kwon et al., 2023) | KV cache paged memory — radiation fault isolation |
| DCTCP (Alizadeh et al., 2010) | TCP baseline for datacenter links |
| FlashAttention (Dao et al., 2022) | Attention tiling on constrained memory hierarchy |
| AWQ (Lin et al., 2024) | Quantization under bandwidth-constrained hardware |
| ShadowKV (Sun et al., 2024) | KV cache offload under memory constraints |
| Message Ferries (Zhao et al., 2004) | Intermittent connectivity networking |
| Snoop Protocol (Balakrishnan et al., 1995) | Link-layer TCP shielding for unreliable links |
| L4S (Briscoe et al., 2023) | Scalable congestion signaling for low-latency links |

## Success Metrics

- TCP throughput degradation curve vs BER (0 to 10^-3)
- Inference throughput (tokens/sec) vs thermal throttle level
- KV cache hit rate vs DRAM bit error rate
- Output faithfulness (ROUGE/perplexity) vs radiation level
- Latency P50/P95/P99 across all conditions

## Target Venues

- SIGCOMM, NSDI (networking track)
- MLSys, OSDI (inference systems track)
- Hot Topics in Space Networking (if applicable)
