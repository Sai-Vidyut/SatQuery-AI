from datetime import date
from unittest.mock import MagicMock

import pytest

from app.adapters.imagery.earth_engine.sentinel2 import query_sentinel2_scenes
from app.core.errors import SatQueryError


def _make_mock_image(system_index: str, time_ms: int, cloud: float):
    image = MagicMock()
    image.id.return_value = system_index
    image.getInfo.return_value = {
        "properties": {
            "system:index": system_index,
            "system:time_start": time_ms,
            "CLOUDY_PIXEL_PERCENTAGE": cloud,
            "SPACECRAFT_NAME": "Sentinel-2A",
            "MGRS_TILE": "43QCD",
        }
    }
    return image


def test_query_sentinel2_scenes_returns_candidates():
    ee = MagicMock()
    client = MagicMock()
    collection = MagicMock()
    filtered = MagicMock()
    client.image_collection.return_value = collection
    collection.filterBounds.return_value = collection
    collection.filterDate.return_value = collection
    collection.filter.return_value = filtered
    filtered.size.return_value.getInfo.return_value = 2

    img1 = _make_mock_image("20240112T050701", 1705037221000, 5.0)
    img2 = _make_mock_image("20240303T050701", 1709453221000, 10.0)
    image_list = MagicMock()
    image_list.get.side_effect = lambda i: f"ref-{i}"
    filtered.toList.return_value = image_list
    ee.Image.side_effect = [img1, img2]
    ee.Filter.lt = MagicMock()

    candidates = query_sentinel2_scenes(
        client=client,
        ee=ee,
        aoi_geometry="aoi-geom",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        cloud_cover_max=30.0,
    )

    assert len(candidates) == 2
    assert candidates[0].scene_id == "20240112T050701"
    assert candidates[0].platform_id == "COPERNICUS/S2_SR_HARMONIZED/20240112T050701"


def test_query_sentinel2_no_scenes_raises():
    ee = MagicMock()
    client = MagicMock()
    collection = MagicMock()
    filtered = MagicMock()
    client.image_collection.return_value = collection
    collection.filterBounds.return_value = collection
    collection.filterDate.return_value = collection
    collection.filter.return_value = filtered
    filtered.size.return_value.getInfo.return_value = 0
    ee.Filter.lt = MagicMock()

    with pytest.raises(SatQueryError) as exc:
        query_sentinel2_scenes(
            client=client,
            ee=ee,
            aoi_geometry="aoi",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            cloud_cover_max=30.0,
        )
    assert exc.value.code == "no_imagery_found"


def test_query_sentinel2_ee_failure_raises():
    ee = MagicMock()
    client = MagicMock()
    client.image_collection.side_effect = RuntimeError("network error")

    with pytest.raises(SatQueryError) as exc:
        query_sentinel2_scenes(
            client=client,
            ee=ee,
            aoi_geometry="aoi",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            cloud_cover_max=30.0,
        )
    assert exc.value.code == "earth_engine_request_failed"
