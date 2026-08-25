from __future__ import annotations

from typing import Any


def mask_sentinel2_sr(image: Any, ee: Any) -> Any:
    """
    Mask clouds, cirrus, and cloud shadows using QA60 and SCL bands.
    COPERNICUS/S2_SR_HARMONIZED provides both.
    """
    qa = image.select("QA60")
    cloud_bit = 1 << 10
    cirrus_bit = 1 << 11
    qa_clear = (
        qa.bitwiseAnd(cloud_bit)
        .eq(0)
        .And(qa.bitwiseAnd(cirrus_bit).eq(0))
    )

    scl = image.select("SCL")
    # 3=shadow, 8=medium cloud, 9=high cloud, 10=thin cirrus
    scl_clear = (
        scl.neq(3)
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
    )

    return image.updateMask(qa_clear.And(scl_clear))
