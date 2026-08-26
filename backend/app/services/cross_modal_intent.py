"""Cross-modal optical + SAR query detection."""

from __future__ import annotations

_CROSS_MODAL_MARKERS = (
    "optical and sar",
    "optical and radar",
    "optical and sar images",
    "optical and radar images",
    "both images",
    "both modalities",
    "use both",
    "together to identify",
    "images together",
    "compare the optical and sar",
    "compare the optical and radar",
    "complementary information",
    "sar image provide",
    "sar provides",
    "built-up and water",
    "built up and water",
    "water-covered",
    "water covered",
    "joint optical",
    "multimodal optical",
    "cross-modal",
    "cross modal",
)


def is_cross_modal_optical_sar_query(query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return False
    if any(marker in q for marker in _CROSS_MODAL_MARKERS):
        return True
    if "optical" in q and ("sar" in q or "radar" in q):
        return True
    return False
