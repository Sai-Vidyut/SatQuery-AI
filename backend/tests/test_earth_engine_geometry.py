import pytest

from app.adapters.imagery.earth_engine.geometry import bbox_from_geometry, geojson_to_ee_geometry
from app.core.errors import SatQueryError
from app.schemas.domain import GeoJSONGeometry


def test_bbox_from_polygon():
    geom = GeoJSONGeometry(
        type="Polygon",
        coordinates=[
            [
                [77.59, 12.97],
                [77.61, 12.97],
                [77.61, 12.99],
                [77.59, 12.99],
                [77.59, 12.97],
            ]
        ],
    )
    bbox = bbox_from_geometry(geom)
    assert bbox == [77.59, 12.97, 77.61, 12.99]


def test_bbox_rejects_point():
    with pytest.raises(SatQueryError) as exc:
        bbox_from_geometry(GeoJSONGeometry(type="Point", coordinates=[77.6, 12.98]))
    assert exc.value.code == "invalid_aoi"


def test_geojson_to_ee_polygon():
    class FakeEE:
        class Geometry:
            @staticmethod
            def Polygon(coords):
                return {"type": "Polygon", "coords": coords}

    geom = GeoJSONGeometry(
        type="Polygon",
        coordinates=[[[0, 0], [1, 0], [1, 1], [0, 0]]],
    )
    result = geojson_to_ee_geometry(FakeEE(), geom)
    assert result["type"] == "Polygon"
