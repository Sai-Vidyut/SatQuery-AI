"""
Bimodal histogram separability confidence for change detection.

This score measures how well-separated changed vs unchanged populations are in the
difference histogram. It is DETECTOR CONFIDENCE / SEPARABILITY — not model accuracy
or classification accuracy.
"""

from __future__ import annotations

import numpy as np


def compute_confidence(
    diff: np.ndarray,
    change_mask: np.ndarray,
    otsu_threshold: float,
    *,
    imbalance_low: float = 0.005,
    imbalance_high: float = 0.60,
    n_bins: int = 256,
) -> float:
    flat = np.nan_to_num(diff.flatten().astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    if flat.size == 0 or float(flat.max() - flat.min()) < 1e-8:
        return 0.0

    omega = _otsu_variance_ratio(flat, otsu_threshold)
    hist, bin_edges = np.histogram(flat, bins=n_bins, density=False)
    hist_smooth = np.convolve(hist.astype(float), np.ones(5) / 5, mode="same")
    valley_score = _valley_score(hist_smooth, bin_edges, otsu_threshold)
    changed_frac = float(change_mask.sum()) / max(change_mask.size, 1)
    imbalance = _imbalance_penalty(changed_frac, low=imbalance_low, high=imbalance_high)

    confidence = float(omega * (1.0 - valley_score) * (1.0 - imbalance))
    if not np.isfinite(confidence):
        return 0.0
    return round(float(np.clip(confidence, 0.0, 1.0)), 4)


def _otsu_variance_ratio(flat: np.ndarray, threshold: float) -> float:
    below = flat[flat <= threshold]
    above = flat[flat > threshold]
    if below.size == 0 or above.size == 0:
        return 0.0

    w0 = len(below) / len(flat)
    w1 = len(above) / len(flat)
    mu0 = below.mean()
    mu1 = above.mean()
    mu = flat.mean()
    inter_var = w0 * (mu0 - mu) ** 2 + w1 * (mu1 - mu) ** 2
    total_var = float(flat.var())
    if total_var < 1e-12:
        return 0.0
    return float(np.clip(inter_var / total_var, 0.0, 1.0))


def _valley_score(hist_smooth: np.ndarray, bin_edges: np.ndarray, threshold: float) -> float:
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    n_bins = len(hist_smooth)
    thresh_bin = int(np.searchsorted(bin_centers, threshold, side="right"))
    thresh_bin = max(1, min(thresh_bin, n_bins - 2))

    left_peak = float(hist_smooth[:thresh_bin].max()) if thresh_bin > 0 else 0.0
    right_peak = float(hist_smooth[thresh_bin:].max()) if thresh_bin < n_bins else 0.0
    valley_val = float(hist_smooth[thresh_bin])
    taller_peak = max(left_peak, right_peak)
    if taller_peak < 1e-8:
        return 1.0
    return float(np.clip(valley_val / taller_peak, 0.0, 1.0))


def _imbalance_penalty(changed_frac: float, *, low: float, high: float) -> float:
    if low <= changed_frac <= high:
        return 0.0
    if changed_frac < low:
        return float(np.clip(1.0 - changed_frac / low, 0.0, 1.0))
    return float(np.clip((changed_frac - high) / (1.0 - high), 0.0, 1.0))
