from __future__ import annotations

import hashlib
import math

from app.schemas.domain import (
    ChangeDetectionInput,
    ChangeDetectionOutput,
    DataMode,
    EvidenceRegion,
    GeoJSONGeometry,
    Metric,
)
from app.adapters.change.base import ChangeDetector


def _bbox(coords: list) -> tuple[float, float, float, float]:
    ring = coords[0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lons), min(lats), max(lons), max(lats)


def _seed_regions(
    bbox: tuple[float, float, float, float],
    earlier: str,
    later: str,
    count: int = 3,
) -> list[EvidenceRegion]:
    min_lon, min_lat, max_lon, max_lat = bbox
    width = max_lon - min_lon
    height = max_lat - min_lat
    digest = hashlib.sha256(f"{bbox}:{earlier}:{later}".encode()).hexdigest()
    regions: list[EvidenceRegion] = []

    for i in range(count):
        h = hashlib.sha256(f"{digest}:{i}".encode()).hexdigest()
        cx = min_lon + width * (int(h[0:4], 16) / 65535 * 0.6 + 0.2)
        cy = min_lat + height * (int(h[4:8], 16) / 65535 * 0.6 + 0.2)
        w = width * 0.12
        hgt = height * 0.10
        confidence = round(0.45 + (int(h[8:12], 16) / 65535) * 0.5, 2)
        area_m2 = w * hgt * 111_320 * 111_320 * math.cos(math.radians(cy))

        poly = GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [cx - w / 2, cy - hgt / 2],
                    [cx + w / 2, cy - hgt / 2],
                    [cx + w / 2, cy + hgt / 2],
                    [cx - w / 2, cy + hgt / 2],
                    [cx - w / 2, cy - hgt / 2],
                ]
            ],
        )
        regions.append(
            EvidenceRegion(
                id=f"region-{i + 1:02d}",
                geometry=poly,
                type="construction_change",
                confidence=confidence,
                metrics=[
                    Metric(
                        name="estimated_area",
                        value=round(area_m2, 1),
                        unit="m²",
                        source="deterministic_change_detector",
                    ),
                    Metric(
                        name="change_magnitude",
                        value=round(confidence * 100, 1),
                        unit="%",
                        source="deterministic_change_detector",
                    ),
                ],
                source="deterministic_change_detector",
                metadata={"detector_version": "0.1.0-dev", "index": i},
            )
        )
    return regions


class DeterministicChangeDetector(ChangeDetector):
    """
    Reproducible change regions for development. Same interface as future ML detectors.
    """

    @property
    def name(self) -> str:
        return "deterministic_change_detector"

    async def detect(self, payload: ChangeDetectionInput) -> ChangeDetectionOutput:
        bbox = _bbox(payload.aoi.geometry.coordinates)
        regions = _seed_regions(
            bbox,
            payload.earlier_date.isoformat(),
            payload.later_date.isoformat(),
        )
        return ChangeDetectionOutput(
            regions=regions,
            raw_detection_count=len(regions),
            detector=self.name,
            mode=payload.imagery.mode,
        )
