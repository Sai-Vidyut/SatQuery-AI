"""Core differencing, STSF-inspired pseudo-change suppression, and Otsu thresholding."""

from __future__ import annotations

import cv2
import numpy as np

IndexArray = np.ndarray


def compute_difference(
    index_t1: IndexArray,
    index_t2: IndexArray,
    *,
    absolute: bool = True,
) -> IndexArray:
    if index_t1.shape != index_t2.shape:
        raise ValueError(
            f"Shape mismatch: T1 {index_t1.shape} vs T2 {index_t2.shape}. "
            "Co-register inputs before differencing."
        )
    diff = index_t2.astype(np.float32) - index_t1.astype(np.float32)
    if absolute:
        diff = np.abs(diff)
    return np.nan_to_num(diff, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def smooth_difference(diff: IndexArray, sigma: float = 1.5) -> IndexArray:
    if sigma <= 0:
        return diff
    ksize = max(3, int(6 * sigma + 1) | 1)
    smoothed = cv2.GaussianBlur(diff, (ksize, ksize), sigma)
    return np.nan_to_num(smoothed, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def suppress_pseudo_changes(
    diff: IndexArray,
    index_t1: IndexArray,
    index_t2: IndexArray,
    *,
    window_size: int = 9,
    uniformity_threshold: float = 0.15,
) -> tuple[IndexArray, int]:
    """
    STSF-inspired pseudo-change suppression.

    This is NOT STSF-Net — it applies a lightweight radiometric-drift filter inspired
    by pseudo-change suppression literature.
    """
    w = window_size
    ksize = (w, w)
    t1f = np.nan_to_num(index_t1.astype(np.float32))
    t2f = np.nan_to_num(index_t2.astype(np.float32))

    mean_t1 = cv2.boxFilter(t1f, ddepth=-1, ksize=ksize, normalize=True)
    mean_t2 = cv2.boxFilter(t2f, ddepth=-1, ksize=ksize, normalize=True)
    mean_sq_t1 = cv2.boxFilter(t1f**2, ddepth=-1, ksize=ksize, normalize=True)
    mean_sq_t2 = cv2.boxFilter(t2f**2, ddepth=-1, ksize=ksize, normalize=True)

    std_t1 = np.sqrt(np.clip(mean_sq_t1 - mean_t1**2, 0, None))
    std_t2 = np.sqrt(np.clip(mean_sq_t2 - mean_t2**2, 0, None))

    signed_diff = t2f - t1f
    mean_delta = cv2.boxFilter(signed_diff, ddepth=-1, ksize=ksize, normalize=True)

    flat_t1 = std_t1 < 0.05
    flat_t2 = std_t2 < 0.05
    large_shift = np.abs(mean_delta) > uniformity_threshold
    pseudo_change_mask = flat_t1 & flat_t2 & large_shift

    n_pseudo = int(pseudo_change_mask.sum())
    suppressed = diff.copy()
    suppressed[pseudo_change_mask] = 0.0
    return (
        np.nan_to_num(suppressed, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32),
        n_pseudo,
    )


def _otsu_numpy(image: np.ndarray, n_bins: int = 256) -> float:
    hist, bin_edges = np.histogram(image.ravel(), bins=n_bins)
    hist = hist.astype(np.float64)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    total = hist.sum()
    if total == 0:
        return 0.0

    prob = hist / total
    w0 = np.cumsum(prob)
    mu0 = np.cumsum(prob * bin_centers) / np.maximum(w0, 1e-12)
    w1 = 1.0 - w0
    mu_total = (prob * bin_centers).sum()
    mu1 = (mu_total - np.cumsum(prob * bin_centers)) / np.maximum(w1, 1e-12)
    inter_class_var = w0 * w1 * (mu0 - mu1) ** 2
    idx = int(np.argmax(inter_class_var))
    return float(bin_centers[idx])


def otsu_threshold(
    diff: IndexArray,
    *,
    percentile_clip: float = 98.0,
) -> tuple[np.ndarray, float]:
    """Adaptive Otsu thresholding with outlier clipping."""
    finite = np.nan_to_num(diff, nan=0.0, posinf=0.0, neginf=0.0)
    if finite.size == 0:
        return np.zeros_like(finite, dtype=bool), 0.0

    clip_val = float(np.percentile(finite, percentile_clip))
    diff_clipped = np.clip(finite, 0, clip_val)

    diff_range = float(diff_clipped.max() - diff_clipped.min())
    if diff_range < 1e-8:
        return np.zeros(diff.shape, dtype=bool), 0.0

    thresh = _otsu_numpy(diff_clipped)
    mask = diff_clipped > thresh
    return mask.astype(bool), float(thresh)


def detect_changes(
    index_t1: IndexArray,
    index_t2: IndexArray,
    *,
    smooth_sigma: float = 1.5,
    suppress_pseudo: bool = True,
    pseudo_window: int = 9,
    pseudo_uniformity_threshold: float = 0.15,
    percentile_clip: float = 98.0,
    use_otsu: bool = True,
) -> dict:
    raw_diff = compute_difference(index_t1, index_t2, absolute=True)
    signed_diff = compute_difference(index_t1, index_t2, absolute=False)
    smooth_diff = smooth_difference(raw_diff, sigma=smooth_sigma)

    if suppress_pseudo:
        suppressed_diff, n_pseudo = suppress_pseudo_changes(
            smooth_diff,
            index_t1,
            index_t2,
            window_size=pseudo_window,
            uniformity_threshold=pseudo_uniformity_threshold,
        )
    else:
        suppressed_diff = smooth_diff
        n_pseudo = 0

    if use_otsu:
        change_mask, thresh = otsu_threshold(suppressed_diff, percentile_clip=percentile_clip)
    else:
        thresh = float(np.percentile(suppressed_diff, 95)) if suppressed_diff.size else 0.0
        change_mask = suppressed_diff > thresh

    return {
        "raw_diff": raw_diff,
        "signed_diff": signed_diff,
        "smooth_diff": smooth_diff,
        "suppressed_diff": suppressed_diff,
        "change_mask": change_mask,
        "otsu_threshold": thresh,
        "n_pseudo_removed": n_pseudo,
    }
