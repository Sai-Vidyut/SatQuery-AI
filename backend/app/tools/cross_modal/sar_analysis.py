"""Uploaded SAR analysis for cross-modal workflows."""

from __future__ import annotations

import hashlib

from app.schemas.cross_modal import CrossModalProviderKind, ModalityAnalysisSummary, SARAnalysisInput
from app.schemas.domain import EvidenceRegion, GeoJSONGeometry, Metric
from app.adapters.imagery.uploaded.bi_temporal_bridge import aoi_from_bounds


class UploadedSARAnalysisTool:
    name = "sar_analysis"
    description = "Extract SAR backscatter/surface-pattern cues from an uploaded image."

    async def execute(self, payload: SARAnalysisInput) -> ModalityAnalysisSummary:
        bounds = payload.bounds
        digest = hashlib.sha256(f"sar:{payload.sar_image_id}:{payload.query}".encode()).hexdigest()[:8]
        aoi = aoi_from_bounds(bounds)
        ring = aoi.geometry.coordinates[0]
        west, south = ring[0][0], ring[0][1]
        east, north = ring[2][0], ring[2][1]
        cx = (west + east) / 2
        cy = (south + north) / 2
        w = (east - west) * 0.2
        h = (north - south) * 0.2
        rough_poly = GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [cx + w * 0.2, cy - h / 2],
                    [cx + w * 1.2, cy - h / 2],
                    [cx + w * 1.2, cy + h / 2],
                    [cx + w * 0.2, cy + h / 2],
                    [cx + w * 0.2, cy - h / 2],
                ]
            ],
        )
        smooth_poly = GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [cx - w, cy - h / 2],
                    [cx, cy - h / 2],
                    [cx, cy + h / 2],
                    [cx - w, cy + h / 2],
                    [cx - w, cy - h / 2],
                ]
            ],
        )
        regions = [
            EvidenceRegion(
                id=f"sar-rough-{digest}",
                geometry=rough_poly,
                type="high_backscatter",
                confidence=0.6,
                metrics=[
                    Metric(name="backscatter_pattern", value="rough_built", source="development_sar_analysis"),
                ],
                source="development_sar_analysis",
                metadata={"evidence_modality": "sar", "pattern": "rough_built"},
            ),
            EvidenceRegion(
                id=f"sar-smooth-{digest}",
                geometry=smooth_poly,
                type="low_backscatter",
                confidence=0.55,
                metrics=[
                    Metric(name="backscatter_pattern", value="smooth_water_like", source="development_sar_analysis"),
                ],
                source="development_sar_analysis",
                metadata={"evidence_modality": "sar", "pattern": "smooth_water_like"},
            ),
        ]
        return ModalityAnalysisSummary(
            modality="sar",
            summary=(
                f"[development mock SAR analysis — not Sentinel-1 GRD pipeline] "
                f"SAR backscatter patterns indicate rough built-like and smooth water-like "
                f"responses in image {payload.sar_image_id} (ref {digest})."
            ),
            analyzer="development_uploaded_sar_analysis",
            provider=CrossModalProviderKind.DEVELOPMENT,
            regions=regions,
            confidence_available=False,
            metadata={"mock": True, "image_id": payload.sar_image_id},
        )
