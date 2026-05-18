"""
KV cache fault injection for space-analog characterization.

Models radiation-induced bit errors in KV cache DRAM and measures
how inference output quality degrades as a function of BER.
Uses NumPy only — no PyTorch dependency required.

Fault modes:
  - Single-event upset (SEU): single bit flip in a KV vector
  - Multi-unit upset (MUU): burst of bit flips across adjacent bits
  - Page-level corruption: entire KV page becomes unreliable
"""

import numpy as np
from dataclasses import dataclass
from typing import Literal


FaultMode = Literal["seu", "muu", "page"]


@dataclass
class FaultConfig:
    ber: float = 1e-6             # bit error rate
    mode: FaultMode = "seu"       # seu | muu | page
    muu_burst_bits: int = 8       # bits flipped per MUU event
    page_size_bytes: int = 4096   # page granularity for page-level faults
    seed: int = 42


class KVCacheFaultInjector:
    """
    Injects bit errors into KV cache arrays to simulate radiation effects.

    KV cache is represented as float32 numpy arrays shaped
    (n_heads, seq_len, head_dim).

    Usage:
        injector = KVCacheFaultInjector(FaultConfig(ber=1e-5, mode="seu"))
        corrupted_k, corrupted_v = injector.inject(k_cache, v_cache)
    """

    def __init__(self, cfg: FaultConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)

    def inject(
        self,
        k_cache: np.ndarray,
        v_cache: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        return self._inject_array(k_cache), self._inject_array(v_cache)

    def _inject_array(self, arr: np.ndarray) -> np.ndarray:
        if self.cfg.ber == 0.0:
            return arr.copy()
        flat = arr.astype(np.float32).flatten().view(np.uint32).copy()
        n_bits = len(flat) * 32
        if self.cfg.mode == "seu":
            flat = self._inject_seu(flat, n_bits)
        elif self.cfg.mode == "muu":
            flat = self._inject_muu(flat, n_bits)
        elif self.cfg.mode == "page":
            flat = self._inject_page(flat)
        return flat.view(np.float32).reshape(arr.shape)

    def _inject_seu(self, flat: np.ndarray, n_bits: int) -> np.ndarray:
        n_errors = self.rng.poisson(n_bits * self.cfg.ber)
        if n_errors == 0:
            return flat
        error_bits = self.rng.integers(0, n_bits, size=int(n_errors))
        for bit in error_bits:
            flat[int(bit) // 32] ^= np.uint32(1 << (int(bit) % 32))
        return flat

    def _inject_muu(self, flat: np.ndarray, n_bits: int) -> np.ndarray:
        n_events = self.rng.poisson(n_bits * self.cfg.ber / self.cfg.muu_burst_bits)
        if n_events == 0:
            return flat
        starts = self.rng.integers(0, max(1, n_bits - self.cfg.muu_burst_bits), size=int(n_events))
        for start in starts:
            for offset in range(self.cfg.muu_burst_bits):
                bit = int(start) + offset
                idx = bit // 32
                if idx < len(flat):
                    flat[idx] ^= np.uint32(1 << (bit % 32))
        return flat

    def _inject_page(self, flat: np.ndarray) -> np.ndarray:
        words_per_page = (self.cfg.page_size_bytes * 8) // 32
        n_pages = len(flat) // words_per_page
        if n_pages == 0:
            return flat
        page_error_prob = 1.0 - (1.0 - self.cfg.ber) ** (words_per_page * 32)
        for i in range(n_pages):
            if self.rng.random() < page_error_prob:
                flat[i * words_per_page:(i + 1) * words_per_page] = 0
        return flat


def scaled_dot_product_attention(
    q: np.ndarray, k: np.ndarray, v: np.ndarray
) -> np.ndarray:
    """Numpy implementation of scaled dot-product attention."""
    scale = k.shape[-1] ** -0.5
    scores = np.matmul(q, k.swapaxes(-2, -1)) * scale
    # Softmax
    scores -= scores.max(axis=-1, keepdims=True)
    weights = np.exp(scores)
    weights /= weights.sum(axis=-1, keepdims=True)
    return np.matmul(weights, v)


def measure_output_degradation(
    original: np.ndarray,
    corrupted: np.ndarray,
) -> dict[str, float]:
    """Compare original and corrupted attention outputs."""
    # Replace NaN/Inf from bit-flip-induced float overflow with 0 before comparing
    orig_safe = np.nan_to_num(original, nan=0.0, posinf=0.0, neginf=0.0)
    corr_safe = np.nan_to_num(corrupted, nan=0.0, posinf=0.0, neginf=0.0)
    corrupted_has_nan = bool(np.any(~np.isfinite(corrupted)))

    diff = orig_safe - corr_safe
    mse = float(np.mean(diff ** 2))
    max_dev = float(np.max(np.abs(diff)))
    o_flat = orig_safe.flatten().astype(np.float64)
    c_flat = corr_safe.flatten().astype(np.float64)
    dot = float(np.dot(o_flat, c_flat))
    norm = float(np.linalg.norm(o_flat) * np.linalg.norm(c_flat))
    cos_sim = dot / norm if norm > 1e-12 else 0.0
    return {
        "mse": mse,
        "max_deviation": max_dev,
        "cosine_similarity": cos_sim,
        "output_changed": mse > 1e-8,
        "nan_overflow": corrupted_has_nan,
    }
