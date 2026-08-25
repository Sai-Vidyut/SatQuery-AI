import pytest
from pydantic import ValidationError

from app.schemas.domain import AOI, GeoJSONGeometry, QueryRequest
from datetime import date


def test_query_requires_later_after_earlier():
    aoi = AOI(
        geometry=GeoJSONGeometry(
            type="Polygon",
            coordinates=[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        )
    )
    with pytest.raises(ValidationError):
        QueryRequest(
            query="test",
            aoi=aoi,
            earlier_date=date(2025, 1, 1),
            later_date=date(2024, 1, 1),
        )
