"""Joint optical+SAR fusion — explicit cross-modal stage (not answer concatenation)."""

from __future__ import annotations

from app.evidence.geometry import overlap_fraction_of_child
from app.schemas.cross_modal import (
    CoRegistrationStatus,
    CrossModalFusionInput,
    CrossModalFusionSummary,
    CrossModalProviderKind,
)
from app.schemas.domain import EvidenceRegion, GeoJSONGeometry, Metric


FUSION_POLICY = "uploaded_cross_modal_fusion_v1.0.0"


def _ring(region: EvidenceRegion) -> list[list[float]]:
    return region.geometry.coordinates[0]


class CrossModalFusionTool:
    name = "cross_modal_fusion"
    description = "Fuse uploaded optical and SAR analyses into joint cross-modal evidence."

    async def execute(
        self,
        payload: CrossModalFusionInput,
    ) -> tuple[CrossModalFusionSummary, list[EvidenceRegion]]:
        optical_regions = payload.optical.regions
        sar_regions = payload.sar.regions
        fused: list[EvidenceRegion] = []
        complementary: list[str] = []

        for o_region in optical_regions:
            o_class = o_region.metadata.get("surface_class", "unknown")
            for s_region in sar_regions:
                s_pattern = s_region.metadata.get("pattern", "unknown")
                overlap = overlap_fraction_of_child(_ring(o_region), _ring(s_region))
                if overlap < 0.05:
                    continue
                fused_conf = round(min(o_region.confidence, s_region.confidence) * 0.95, 3)
                claim = "none"
                if o_class == "built_up" and s_pattern == "rough_built":
                    claim = "built_up_supported_optical_sar"
                    complementary.append(
                        "SAR rough backscatter supports optical built-up cue where patterns overlap."
                    )
                elif o_class == "water" and s_pattern == "smooth_water_like":
                    claim = "water_supported_optical_sar"
                    complementary.append(
                        "SAR smooth low-backscatter response supports optical water cue where patterns overlap."
                    )
                else:
                    complementary.append(
                        f"Optical {o_class} and SAR {s_pattern} overlap with partial agreement."
                    )
                fused.append(
                    EvidenceRegion(
                        id=f"fused-{o_region.id}-{s_region.id}",
                        geometry=o_region.geometry,
                        type="cross_modal_fusion",
                        confidence=fused_conf,
                        metrics=[
                            Metric(name="optical_class", value=str(o_class), source="cross_modal_fusion"),
                            Metric(name="sar_pattern", value=str(s_pattern), source="cross_modal_fusion"),
                            Metric(name="overlap_fraction", value=round(overlap, 3), source="cross_modal_fusion"),
                        ],
                        source="cross_modal_fusion",
                        metadata={
                            "evidence_type": "cross_modal_fusion",
                            "evidence_modality": "optical+sar",
                            "claim_type": claim,
                            "fusion_policy": FUSION_POLICY,
                            "optical_region_id": o_region.id,
                            "sar_region_id": s_region.id,
                        },
                    )
                )

        coreg_note = (
            "Benchmark co-registration declared for this pair."
            if payload.co_registration_status == CoRegistrationStatus.VERIFIED_BENCHMARK
            else "Co-registration not verified; fusion uses overlap-only spatial agreement."
        )
        q = payload.query.lower()
        if "complementary" in q:
            complementary.insert(
                0,
                "SAR adds backscatter texture cues that optical reflectance alone cannot isolate.",
            )
        if "built" in q and "water" in q:
            complementary.insert(
                0,
                "Joint analysis targets built-up and water-covered classes using complementary modalities.",
            )

        summary = CrossModalFusionSummary(
            summary=(
                f"Cross-modal fusion produced {len(fused)} joint region(s) from optical and SAR specialists. "
                f"{coreg_note}"
            ),
            fusion_policy=FUSION_POLICY,
            fused_region_count=len(fused),
            complementary_notes=complementary,
            metadata={
                "provider": CrossModalProviderKind.DEVELOPMENT.value,
                "optical_analyzer": payload.optical.analyzer,
                "sar_analyzer": payload.sar.analyzer,
                "co_registration_status": payload.co_registration_status.value,
            },
        )
        return summary, fused
