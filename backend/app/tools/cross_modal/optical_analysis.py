"""Uploaded optical/multispectral analysis for cross-modal workflows."""

from __future__ import annotations

import hashlib

from app.schemas.cross_modal import CrossModalProviderKind, ModalityAnalysisSummary, OpticalAnalysisInput
from app.schemas.domain import EvidenceRegion, GeoJSONGeometry, Metric
from app.adapters.imagery.uploaded.bi_temporal_bridge import aoi_from_bounds


class UploadedOpticalAnalysisTool:
    name = "optical_analysis"
    description = "Extract optical/multispectral surface cues from an uploaded image."

    async def execute(self, payload: OpticalAnalysisInput) -> ModalityAnalysisSummary:
        bounds = payload.bounds
        digest = hashlib.sha256(f"optical:{payload.optical_image_id}:{payload.query}".encode()).hexdigest()[:8]
        aoi = aoi_from_bounds(bounds)
        ring = aoi.geometry.coordinates[0]
        west, south = ring[0][0], ring[0][1]
        east, north = ring[2][0], ring[2][1]
        cx = (west + east) / 2
        cy = (south + north) / 2
        w = (east - west) * 0.25
        h = (north - south) * 0.25
        built_poly = GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [cx - w / 2, cy - h / 2],
                    [cx + w / 2, cy - h / 2],
                    [cx + w / 2, cy + h / 2],
                    [cx - w / 2, cy + h / 2],
                    [cx - w / 2, cy - h / 2],
                ]
            ],
        )
        water_cy = cy - h
        water_poly = GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [cx - w / 2, water_cy - h / 4],
                    [cx + w / 2, water_cy - h / 4],
                    [cx + w / 2, water_cy + h / 4],
                    [cx - w / 2, water_cy + h / 4],
                    [cx - w / 2, water_cy - h / 4],
                ]
            ],
        )
        regions = [
            EvidenceRegion(
                id=f"optical-built-{digest}",
                geometry=built_poly,
                type="built_up_candidate",
                confidence=0.62,
                metrics=[
                    Metric(name="surface_class", value="built_up", source="development_optical_analysis"),
                ],
                source="development_optical_analysis",
                metadata={"evidence_modality": "optical", "surface_class": "built_up"},
            ),
            EvidenceRegion(
                id=f"optical-water-{digest}",
                geometry=water_poly,
                type="water_candidate",
                confidence=0.58,
                metrics=[
                    Metric(name="surface_class", value="water", source="development_optical_analysis"),
                ],
                source="development_optical_analysis",
                metadata={"evidence_modality": "optical", "surface_class": "water"},
            ),
        ]
        q = payload.query.lower()
        focus = []
        if "built" in q:
            focus.append("built-up")
        if "water" in q:
            focus.append("water")
        focus_clause = f" focusing on {', '.join(focus)}" if focus else ""
        return ModalityAnalysisSummary(
            modality="optical",
            summary=(
                f"[development mock optical analysis — not Earth Engine/Dynamic World] "
                f"Optical cues suggest built-up and water-covered candidates{focus_clause} "
                f"in image {payload.optical_image_id} (ref {digest})."
            ),
            analyzer="development_uploaded_optical_analysis",
            provider=CrossModalProviderKind.DEVELOPMENT,
            regions=regions,
            confidence_available=False,
            metadata={"mock": True, "image_id": payload.optical_image_id},
        )
