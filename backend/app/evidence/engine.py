from __future__ import annotations

from app.schemas.domain import (
    ChangeDetectionOutput,
    FuseEvidenceOutput,
    GenerateEvidenceInput,
    GenerateEvidenceOutput,
    ImageryRequest,
    Metric,
    QueryRequest,
    SemanticAnalysisOutput,
)
from app.tools.evidence.fuse_evidence import FuseEvidenceTool
from app.tools.evidence.generate_evidence import GenerateEvidenceTool
from app.tools.imagery.fetch_imagery import FetchImageryTool
from app.tools.temporal.detect_change import DetectChangeTool


class EvidenceEngine:
    """
    Consumes structured tool outputs. Never invents measurements.
    """

    def __init__(self) -> None:
        self._fuse_tool = FuseEvidenceTool()
        self._evidence_tool = GenerateEvidenceTool()

    async def build(
        self,
        query: str,
        detections: ChangeDetectionOutput,
        imagery_mode_source: tuple[str, str],
        semantic: SemanticAnalysisOutput | None = None,
        sar_detections: ChangeDetectionOutput | None = None,
    ) -> GenerateEvidenceOutput:
        from app.schemas.domain import DataMode, FuseEvidenceInput, ImageryResult, SensorType, SpatialMetadata

        mode_str, source = imagery_mode_source
        imagery_stub = ImageryResult(
            source=source,
            mode=DataMode(mode_str),
            sensor=SensorType.SENTINEL_2,
            scenes=[],
            spatial=SpatialMetadata(bbox=[0, 0, 0, 0]),
        )
        fused = await self._fuse_tool.execute(
            FuseEvidenceInput(
                cva_detections=detections,
                semantic=semantic,
                sar_detections=sar_detections,
            )
        )
        return await self._evidence_tool.execute(
            GenerateEvidenceInput(
                query=query,
                imagery=imagery_stub,
                fused_regions=fused.regions,
                fusion_metadata=fused.fusion_metadata,
            )
        )

    def fuse_regions(
        self,
        detections: ChangeDetectionOutput,
        semantic: SemanticAnalysisOutput | None = None,
        sar_detections: ChangeDetectionOutput | None = None,
    ):
        from app.evidence.multimodal_fusion import fuse_multimodal_evidence

        return fuse_multimodal_evidence(detections.regions, semantic, sar_detections)

    def aggregate_metrics(
        self,
        evidence_metrics: list[Metric],
        detections: ChangeDetectionOutput,
        semantic: SemanticAnalysisOutput | None = None,
        sar_detections: ChangeDetectionOutput | None = None,
        fusion_metadata: dict | None = None,
    ) -> list[Metric]:
        metrics = evidence_metrics + [
            Metric(
                name="detector",
                value=detections.detector,
                unit=None,
                source="pipeline",
            ),
            Metric(
                name="raw_detection_count",
                value=detections.raw_detection_count,
                unit="regions",
                source=detections.detector,
            ),
        ]
        if semantic is not None:
            metrics.append(
                Metric(
                    name="semantic_analyzer_pipeline",
                    value=semantic.analyzer,
                    unit=None,
                    source="pipeline",
                )
            )
        if sar_detections is not None:
            metrics.append(
                Metric(
                    name="sar_detector_pipeline",
                    value=sar_detections.detector,
                    unit=None,
                    source="pipeline",
                )
            )
            metrics.append(
                Metric(
                    name="sar_raw_detection_count",
                    value=sar_detections.raw_detection_count,
                    unit="regions",
                    source=sar_detections.detector,
                )
            )
        if fusion_metadata:
            metrics.append(
                Metric(
                    name="fusion_policy_pipeline",
                    value=fusion_metadata.get("fusion_policy", "unknown"),
                    unit=None,
                    source="pipeline",
                )
            )
        return metrics
