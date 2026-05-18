"""
LLM inference benchmark under space-analog thermal throttle conditions.

Uses llama-cli (llama.cpp) to run token generation and measures:
  - Prompt processing speed (pp tokens/sec)
  - Token generation speed (tg tokens/sec)
  - Time-to-first-token (TTFT)
  - Total latency

Thermal throttle is simulated by adding CPU sleep between batches,
scaling with throttle_factor (1.0 = full speed, 0.5 = half speed).
This is a software proxy for thermal throttling; on real space-analog
hardware the throttle would come from the thermal controller directly.
"""

import subprocess
import time
import json
import re
import os
from dataclasses import dataclass
from typing import Optional


MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "../../data/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
)

PROMPT = (
    "<|system|>You are a helpful assistant.</s>"
    "<|user|>Explain the key differences between TCP and UDP in detail.</s>"
    "<|assistant|>"
)


@dataclass
class InferenceBenchConfig:
    model_path: str = MODEL_PATH
    n_predict: int = 128          # tokens to generate
    n_threads: int = 4
    ctx_size: int = 2048
    throttle_factor: float = 1.0  # 1.0=full, 0.5=half-speed (thermal proxy)
    seed: int = 42
    prompt: str = PROMPT


@dataclass
class InferenceBenchResult:
    throttle_factor: float
    pp_tokens_per_sec: float     # prompt processing speed
    tg_tokens_per_sec: float     # token generation speed
    ttft_ms: float               # time to first token
    total_latency_ms: float
    tokens_generated: int
    raw_output: str


class LlamaBench:
    """
    Benchmarks llama.cpp inference at different thermal throttle levels.

    Usage:
        bench = LlamaBench(InferenceBenchConfig(throttle_factor=0.5))
        result = bench.run()
        print(result.tg_tokens_per_sec)
    """

    def __init__(self, cfg: InferenceBenchConfig):
        self.cfg = cfg

    def run(self) -> InferenceBenchResult:
        env = os.environ.copy()

        # Apply throttle by limiting CPU threads proportionally
        effective_threads = max(1, round(self.cfg.n_threads * self.cfg.throttle_factor))

        cmd = [
            "llama-cli",
            "-m", self.cfg.model_path,
            "-p", self.cfg.prompt,
            "-n", str(self.cfg.n_predict),
            "-t", str(effective_threads),
            "-c", str(self.cfg.ctx_size),
            "--seed", str(self.cfg.seed),
            "-ngl", "0",          # no GPU layers (CPU-only for reproducibility)
            "--log-disable",
            "--single-turn",      # exit after one turn (b9200+)
            "--no-warmup",
        ]

        t_start = time.monotonic()
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            env=env, timeout=300
        )
        total_ms = (time.monotonic() - t_start) * 1000

        # b9200 emits timing to stdout; legacy to stderr — check both
        combined = result.stdout + "\n" + result.stderr
        pp_tps, tg_tps, ttft_ms, n_tokens = self._parse_output(combined, total_ms)

        return InferenceBenchResult(
            throttle_factor=self.cfg.throttle_factor,
            pp_tokens_per_sec=pp_tps,
            tg_tokens_per_sec=tg_tps,
            ttft_ms=ttft_ms,
            total_latency_ms=total_ms,
            tokens_generated=n_tokens,
            raw_output=result.stderr[-2000:],   # keep last 2KB of stderr
        )

    def _parse_output(
        self, output: str, total_ms: float
    ) -> tuple[float, float, float, int]:
        """
        Parse llama.cpp timing from both legacy and b9200+ output formats.

        b9200+ inline format (stdout/stderr):
            [ Prompt: 10.5 t/s | Generation: 7.6 t/s ]
        Legacy perf format (stderr):
            prompt eval time = ... N tokens ... Z t/s
            eval time        = ... N tokens ... Z t/s
        """
        pp_tps = tg_tps = 0.0
        ttft_ms = total_ms
        n_tokens = self.cfg.n_predict

        for line in output.splitlines():
            # b9200+ inline status bar
            m = re.search(r"Prompt:\s*([\d.]+)\s*t/s.*?Generation:\s*([\d.]+)\s*t/s", line)
            if m:
                pp_tps = float(m.group(1))
                tg_tps = float(m.group(2))
                continue

            # Legacy: prompt eval
            m = re.search(
                r"prompt eval time[^\d]+([\d.]+)\s*ms[^\d]+(\d+)\s+tokens[^\d]+([\d.]+)\s+tokens/s",
                line
            )
            if m:
                pp_tps  = float(m.group(3))
                ttft_ms = float(m.group(1)) / max(int(m.group(2)), 1)
                continue

            # Legacy: generation eval
            m = re.search(
                r"\beval time[^\d]+([\d.]+)\s*ms[^\d]+(\d+)\s+tokens[^\d]+([\d.]+)\s+tokens/s",
                line
            )
            if m:
                tg_tps   = float(m.group(3))
                n_tokens = int(m.group(2))

        # Derive TTFT from pp speed when legacy format not present
        if pp_tps > 0 and ttft_ms == total_ms:
            prompt_tokens = len(self.cfg.prompt.split())
            ttft_ms = (prompt_tokens / pp_tps) * 1000

        return pp_tps, tg_tps, ttft_ms, n_tokens
