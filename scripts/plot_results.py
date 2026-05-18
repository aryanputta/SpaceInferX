"""
Plot SpaceInferX experiment results.

Usage:
    python3 scripts/plot_results.py --tcp results/space_analog/tcp_ber_sweep.json
    python3 scripts/plot_results.py --kv results/space_analog/kvcache_fault_sweep.json
    python3 scripts/plot_results.py --all
"""

import argparse
import json
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


def plot_tcp_sweep(path: str):
    with open(path) as f:
        data = json.load(f)

    bers = [d["ber"] for d in data]
    throughputs = [d["throughput_mbps"] for d in data]
    p50s = [d["p50_ms"] for d in data]
    p99s = [d["p99_ms"] for d in data]
    loss_rates = [d["packet_loss_rate"] * 100 for d in data]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("TCP Degradation Under Space-Analog Radiation BER", fontsize=13)

    ber_labels = [f"{b:.0e}" if b > 0 else "0" for b in bers]

    ax = axes[0]
    ax.plot(range(len(bers)), throughputs, "o-", color="#2563eb")
    ax.set_xticks(range(len(bers)))
    ax.set_xticklabels(ber_labels, rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("BER (radiation-induced)")
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_title("Throughput vs BER")
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(range(len(bers)), p50s, "o-", label="P50", color="#16a34a")
    ax.plot(range(len(bers)), p99s, "s--", label="P99", color="#dc2626")
    ax.set_xticks(range(len(bers)))
    ax.set_xticklabels(ber_labels, rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("BER (radiation-induced)")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Latency vs BER")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.plot(range(len(bers)), loss_rates, "o-", color="#9333ea")
    ax.set_xticks(range(len(bers)))
    ax.set_xticklabels(ber_labels, rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("BER (radiation-induced)")
    ax.set_ylabel("Packet Loss Rate (%)")
    ax.set_title("Packet Loss vs BER")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = path.replace(".json", "_plot.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


def plot_kvcache_sweep(path: str):
    with open(path) as f:
        data = json.load(f)

    modes = list(dict.fromkeys(d["mode"] for d in data))
    colors = {"seu": "#2563eb", "muu": "#16a34a", "page": "#dc2626"}

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.suptitle("KV Cache Degradation Under Radiation Bit Errors", fontsize=13)

    for mode in modes:
        subset = [d for d in data if d["mode"] == mode]
        bers = [d["ber"] for d in subset]
        cos_sims = [d["cosine_similarity"] for d in subset]
        mses = [d["mse"] for d in subset]
        ber_labels = [f"{b:.0e}" if b > 0 else "0" for b in bers]

        axes[0].plot(range(len(bers)), cos_sims, "o-", label=mode.upper(),
                     color=colors.get(mode, "gray"))
        axes[1].plot(range(len(bers)), mses, "o-", label=mode.upper(),
                     color=colors.get(mode, "gray"))

    for ax, ylabel, title in zip(
        axes,
        ["Cosine Similarity (output vs clean)", "MSE (output vs clean)"],
        ["Output Cosine Similarity vs BER", "Output MSE vs BER"],
    ):
        ax.set_xticks(range(len(bers)))
        ax.set_xticklabels(ber_labels, rotation=45, ha="right", fontsize=8)
        ax.set_xlabel("BER (radiation-induced)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = path.replace(".json", "_plot.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


def plot_inference_sweep(path: str):
    with open(path) as f:
        data = json.load(f)

    throttles = [d["throttle_factor"] for d in data]
    tg_tps    = [d["tg_tokens_per_sec"] for d in data]
    pp_tps    = [d["pp_tokens_per_sec"] for d in data]
    ttfts     = [d["ttft_ms"] for d in data]
    latencies = [d["total_latency_ms"] / 1000 for d in data]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("LLM Inference Under Space-Analog Thermal Throttling (TinyLlama-1.1B Q4)", fontsize=12)

    xs = [f"{t:.1f}" for t in throttles]

    ax = axes[0]
    ax.plot(xs, pp_tps, "o-", label="Prompt (PP)", color="#2563eb")
    ax.plot(xs, tg_tps, "s--", label="Generation (TG)", color="#16a34a")
    ax.set_xlabel("Throttle Factor (1.0 = full speed)")
    ax.set_ylabel("Tokens / sec")
    ax.set_title("Throughput vs Throttle")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(xs, ttfts, "o-", color="#dc2626")
    ax.set_xlabel("Throttle Factor")
    ax.set_ylabel("TTFT (ms)")
    ax.set_title("Time-to-First-Token vs Throttle")
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.plot(xs, latencies, "o-", color="#9333ea")
    ax.set_xlabel("Throttle Factor")
    ax.set_ylabel("Total Latency (s)")
    ax.set_title("Total Inference Latency vs Throttle")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = path.replace(".json", "_plot.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


def plot_kernel_tcp(path: str):
    with open(path) as f:
        data = json.load(f)

    clean = [d for d in data if "error" not in d]
    if not clean:
        print(f"No clean data in {path}")
        return

    bers          = [d["ber"] for d in clean]
    throughputs   = [d["throughput_mbps"] for d in clean]
    retransmits   = [d["retransmits"] for d in clean]
    rtts          = [d["mean_rtt_ms"] for d in clean]
    ber_labels    = [f"{b:.0e}" if b > 0 else "0" for b in bers]
    xs            = range(len(bers))

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("TCP Degradation — Kernel-Level (iperf3 + dummynet)", fontsize=12)

    for ax, ys, ylabel, title, color in zip(
        axes,
        [throughputs, retransmits, rtts],
        ["Throughput (Mbps)", "TCP Retransmits", "Mean RTT (ms)"],
        ["Throughput vs BER", "Retransmits vs BER", "RTT vs BER"],
        ["#2563eb", "#dc2626", "#16a34a"],
    ):
        ax.plot(list(xs), ys, "o-", color=color)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(ber_labels, rotation=45, ha="right", fontsize=8)
        ax.set_xlabel("BER (radiation-induced)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = path.replace(".json", "_plot.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


def plot_orbit_tcp(path: str):
    with open(path) as f:
        data = json.load(f)

    orbits = [d["orbit"] for d in data]
    goodputs = [d["goodput_mbps"] for d in data]
    rtts_p50 = [d["rtt_p50_ms"] for d in data]
    rtts_p99 = [d["rtt_p99_ms"] for d in data]
    efficiencies = [d["goodput_efficiency"] * 100 for d in data]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("TCP Goodput by Orbit — Space-Analog Link Conditions", fontsize=13)
    xs = range(len(orbits))

    ax = axes[0]
    ax.bar(xs, goodputs, color=["#2563eb", "#16a34a", "#9333ea", "#dc2626"])
    ax.set_xticks(list(xs))
    ax.set_xticklabels(orbits, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Goodput (Mbps)")
    ax.set_title("Goodput by Orbit")
    ax.grid(True, alpha=0.3, axis="y")

    ax = axes[1]
    ax.bar(xs, rtts_p50, label="P50", color="#2563eb", alpha=0.7)
    ax.bar(xs, rtts_p99, label="P99", color="#dc2626", alpha=0.5)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(orbits, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("RTT (ms)")
    ax.set_title("RTT Distribution by Orbit")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    ax = axes[2]
    ax.bar(xs, efficiencies, color="#16a34a")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(orbits, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Goodput Efficiency (%)")
    ax.set_title("Goodput / Theoretical Max")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    out = path.replace(".json", "_plot.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


def plot_orbital_thermal(path: str):
    with open(path) as f:
        data = json.load(f)

    orbits = [d["orbit"] for d in data]
    t_max_active = [d["active_load"]["t_max_c"] for d in data]
    t_min_active = [d["active_load"]["t_min_c"] for d in data]
    ss_sun = [d["steady_state"]["full_sun_active_c"] for d in data]
    ss_eclipse = [d["steady_state"]["eclipse_active_c"] for d in data]
    radiator_req = [d["radiator_area_required_cm2"] for d in data]
    radiator_have = data[0]["current_radiator_cm2"]
    throttle_min = [d["active_load"]["throttle_min"] for d in data]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("Orbital Thermal Profile — 1U Passive-Cooled Compute Module (5W TDP)", fontsize=12)
    xs = range(len(orbits))

    ax = axes[0]
    ax.bar(xs, ss_sun, label="Full sun (active)", color="#dc2626", alpha=0.8)
    ax.bar(xs, ss_eclipse, label="Eclipse (active)", color="#2563eb", alpha=0.8)
    ax.axhline(y=85, color="black", linestyle="--", linewidth=1, label="T_max = 85°C")
    ax.axhline(y=70, color="orange", linestyle=":", linewidth=1, label="Throttle = 70°C")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(orbits, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Temperature (°C)")
    ax.set_title("Steady-State Temperature")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3, axis="y")

    ax = axes[1]
    ax.bar(xs, radiator_req, label="Required", color="#dc2626", alpha=0.8)
    ax.axhline(y=radiator_have, color="#2563eb", linestyle="--", linewidth=2,
               label=f"Available ({radiator_have:.0f} cm²)")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(orbits, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Radiator Area (cm²)")
    ax.set_title("Radiator Area: Required vs Available")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    ax = axes[2]
    ax.bar(xs, [t * 100 for t in throttle_min], color="#16a34a")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(orbits, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Min Throttle Level (%)")
    ax.set_ylim(0, 110)
    ax.set_title("Worst-Case Throttle in 3-Orbit Sim")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    out = path.replace(".json", "_plot.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tcp",      help="Simulated TCP BER sweep JSON")
    parser.add_argument("--tcp-kern", help="Kernel TCP sweep JSON (iperf3+dummynet)")
    parser.add_argument("--tcp-orbit", help="Orbit TCP sweep JSON")
    parser.add_argument("--kv",       help="KV cache fault sweep JSON")
    parser.add_argument("--inf",      help="Inference throttle sweep JSON")
    parser.add_argument("--thermal",  help="Orbital thermal sweep JSON")
    parser.add_argument("--all",      action="store_true", help="Plot all available results")
    args = parser.parse_args()

    if args.all or args.tcp:
        p = args.tcp or "results/space_analog/tcp_ber_sweep.json"
        if os.path.exists(p): plot_tcp_sweep(p)
        else: print(f"Not found: {p}")

    if args.all or args.tcp_kern:
        p = getattr(args, "tcp_kern", None) or "results/space_analog/tcp_kernel_sweep.json"
        if os.path.exists(p): plot_kernel_tcp(p)
        else: print(f"Not found: {p} — run kernel TCP sweep with sudo first")

    if args.all or args.tcp_orbit:
        p = getattr(args, "tcp_orbit", None) or "results/space_analog/tcp_orbit_sweep.json"
        if os.path.exists(p): plot_orbit_tcp(p)
        else: print(f"Not found: {p}")

    if args.all or args.kv:
        p = args.kv or "results/space_analog/kvcache_fault_sweep.json"
        if os.path.exists(p): plot_kvcache_sweep(p)
        else: print(f"Not found: {p}")

    if args.all or args.inf:
        p = args.inf or "results/space_analog/inference_throttle_sweep.json"
        if os.path.exists(p): plot_inference_sweep(p)
        else: print(f"Not found: {p} — run inference sweep first")

    if args.all or args.thermal:
        p = getattr(args, "thermal", None) or "results/space_analog/orbital_thermal_sweep.json"
        if os.path.exists(p): plot_orbital_thermal(p)
        else: print(f"Not found: {p}")


if __name__ == "__main__":
    main()
