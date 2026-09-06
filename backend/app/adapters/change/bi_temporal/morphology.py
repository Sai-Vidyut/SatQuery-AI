"""Morphological cleanup and connected-component labelling."""

from __future__ import annotations

import cv2
import numpy as np


def _disk_kernel(radius: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))


def clean_mask(
    mask: np.ndarray,
    *,
    open_radius: int = 2,
    close_radius: int = 3,
    min_area_px: int = 25,
) -> np.ndarray:
    cleaned = mask.astype(np.uint8)

    if open_radius > 0:
        kernel = _disk_kernel(open_radius)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

    if close_radius > 0:
        kernel = _disk_kernel(close_radius)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        cleaned, connectivity=8, ltype=cv2.CV_32S
    )
    for lbl in range(1, num_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if area < min_area_px:
            cleaned[labels == lbl] = 0

    return cleaned.astype(bool)


def label_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    num_labels, labeled = cv2.connectedComponents(
        mask.astype(np.uint8), connectivity=8, ltype=cv2.CV_32S
    )
    return labeled, max(num_labels - 1, 0)
