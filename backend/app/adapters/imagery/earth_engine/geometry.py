from __future__ import annotations

from typing import Any

from app.core.errors import SatQueryError
from app.schemas.domain import GeoJSONGeometry


def geojson_to_ee_geometry(ee: Any, geometry: GeoJSONGeometry) -> Any:
    """Convert GeoJSON geometry to an Earth Engine Geometry."""
    coords = geometry.coordinates
    if geometry.type == "Polygon":
        return ee.Geometry.Polygon(coords)
    if geometry.type == "MultiPolygon":
        return ee.Geometry.MultiPolygon(coords)
    raise SatQueryError(
        "invalid_aoi",
        f"AOI geometry type '{geometry.type}' is not supported. Use Polygon or MultiPolygon.",
        status_code=400,
        field="aoi.geometry",
    )


def bbox_from_geometry(geometry: GeoJSONGeometry) -> list[float]:
    """Compute [min_lon, min_lat, max_lon, max_lat] from GeoJSON polygon coordinates."""
    if geometry.type == "Polygon":
        rings = [geometry.coordinates]
    elif geometry.type == "MultiPolygon":
        rings = geometry.coordinates
    else:
        raise SatQueryError(
            "invalid_aoi",
            f"Cannot compute bbox for geometry type '{geometry.type}'.",
            status_code=400,
            field="aoi.geometry",
        )

    lons: list[float] = []
    lats: list[float] = []
    for polygon in rings:
        ring = polygon[0] if polygon else []
        for point in ring:
            if len(point) < 2:
                continue
            lons.append(float(point[0]))
            lats.append(float(point[1]))

    if not lons or not lats:
        raise SatQueryError(
            "invalid_aoi",
            "AOI geometry has no valid coordinates.",
            status_code=400,
            field="aoi.geometry",
        )

    return [min(lons), min(lats), max(lons), max(lats)]
