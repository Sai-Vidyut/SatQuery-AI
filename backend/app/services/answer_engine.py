from __future__ import annotations

from app.schemas.domain import DataMode, GenerateEvidenceOutput, QueryRequest, SensorType
from app.services.query_profiles import BUILDING_CONSTRUCTION_PROFILE


class AnswerEngine:
    """Template-based explanations from validated evidence. No invented numbers."""

    def compose(
        self,
        request: QueryRequest,
        evidence: GenerateEvidenceOutput,
        mode: DataMode,
        *,
        analysis_profile: str | None = None,
        fusion_metadata: dict | None = None,
    ) -> str:
        cva_count = sum(
            1
            for r in evidence.regions
            if r.metadata.get("evidence_type") == "spectral_change"
            or (
                r.metadata.get("claim_type", "none") == "none"
                and r.metadata.get("evidence_modality") == "optical"
            )
        )
        sar_count = sum(1 for r in evidence.regions if r.metadata.get("evidence_type") == "sar_change")
        multimodal_count = sum(1 for r in evidence.regions if r.metadata.get("evidence_type") == "multimodal_change")
        candidate_count = sum(
            1
            for r in evidence.regions
            if r.metadata.get("claim_type") in ("construction_candidate", "new_built_area")
        )
        total = len(evidence.regions)

        if total == 0:
            return (
                f"No significant change detected in the AOI for "
                f"{request.earlier_date.isoformat()} to {request.later_date.isoformat()}."
            )

        pct = round(evidence.confidence * 100)
        mode_note = (
            " (development demo data)"
            if mode == DataMode.DEVELOPMENT
            else ""
        )

        if request.sensor == SensorType.SENTINEL_1 and not multimodal_count and not candidate_count:
            count = sar_count or total
            return (
                f"Found {count} significant SAR radar backscatter change region"
                f"{'s' if count != 1 else ''} matching your query "
                f"\"{request.query.strip()}\" between {request.earlier_date.isoformat()} and "
                f"{request.later_date.isoformat()}. "
                f"This is radar change evidence only — not flood, construction, or damage confirmation. "
                f"Mean confidence {pct}%.{mode_note}"
            )

        if analysis_profile == BUILDING_CONSTRUCTION_PROFILE and candidate_count > 0:
            sar_support = sum(
                1 for r in evidence.regions
                if r.metadata.get("claim_type") == "construction_candidate"
                and r.metadata.get("evidence_modality") == "optical+semantic+sar"
            )
            sar_clause = (
                f" {sar_support} include supporting SAR radar evidence."
                if sar_support
                else ""
            )
            return (
                f"Found {candidate_count} construction candidate{'s' if candidate_count != 1 else ''} "
                f"supported by spectral change and semantic built-area evidence, out of "
                f"{cva_count} significant spectral change region{'s' if cva_count != 1 else ''}"
                f"{f', with {multimodal_count} multimodal optical+SAR change region' + ('s' if multimodal_count != 1 else '') if multimodal_count else ''}"
                f", and {sar_count} SAR-only region{'s' if sar_count != 1 else ''}."
                f"{sar_clause} "
                f"Query: \"{request.query.strip()}\" between "
                f"{request.earlier_date.isoformat()} and {request.later_date.isoformat()}. "
                f"Mean confidence {pct}%.{mode_note}"
            )

        if multimodal_count > 0:
            return (
                f"Found {cva_count} spectral change region{'s' if cva_count != 1 else ''}, "
                f"{multimodal_count} multimodal optical+SAR change region{'s' if multimodal_count != 1 else ''}, "
                f"and {sar_count} SAR-only region{'s' if sar_count != 1 else ''} "
                f"for your query \"{request.query.strip()}\" between "
                f"{request.earlier_date.isoformat()} and {request.later_date.isoformat()}. "
                f"No semantic construction claims were made from SAR alone. "
                f"Mean confidence {pct}%.{mode_note}"
            )

        if analysis_profile == BUILDING_CONSTRUCTION_PROFILE:
            return (
                f"Found {cva_count} significant spectral change region{'s' if cva_count != 1 else ''} "
                f"for your query \"{request.query.strip()}\" between "
                f"{request.earlier_date.isoformat()} and {request.later_date.isoformat()}. "
                f"No construction candidates were supported by semantic built-area evidence. "
                f"Mean confidence {pct}%.{mode_note}"
            )

        return (
            f"Found {cva_count or total} significant spectral change region"
            f"{'s' if (cva_count or total) != 1 else ''} matching your query "
            f"\"{request.query.strip()}\" between {request.earlier_date.isoformat()} and "
            f"{request.later_date.isoformat()}. Mean confidence {pct}%.{mode_note}"
        )
