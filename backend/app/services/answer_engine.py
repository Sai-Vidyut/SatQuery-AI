from __future__ import annotations

from app.schemas.bi_temporal_change import BiTemporalChangeResult
from app.schemas.cross_modal import CrossModalOpticalSARResult
from app.schemas.domain import DataMode, GenerateEvidenceOutput, QueryRequest, SensorType
from app.schemas.imagery_policy import ImageryPolicyReport, PolicyDecision
from app.schemas.vqa import SingleImageCaptionResult, SingleImageVQAResult, VQAProviderKind
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

    def compose_vqa(self, request: QueryRequest, vqa: SingleImageVQAResult) -> str:
        """Return the model narrative without inventing spatial evidence."""
        provider_note = ""
        if vqa.provider == VQAProviderKind.DEVELOPMENT:
            provider_note = " [development mock provider — not real GeoChat inference]"
        elif vqa.model_name == "MBZUAI/geochat-7B":
            provider_note = f" [model: {vqa.model_name}]"
        else:
            provider_note = f" [model: {vqa.model_name}, provider: {vqa.provider.value}]"
        return f"{vqa.answer.strip()}{provider_note}"

    def compose_caption(self, request: QueryRequest, caption: SingleImageCaptionResult) -> str:
        """Return the scene description without inventing spatial evidence."""
        provider_note = ""
        if caption.provider == VQAProviderKind.DEVELOPMENT:
            provider_note = " [development mock provider — not real GeoChat inference]"
        elif caption.model_name == "MBZUAI/geochat-7B":
            provider_note = f" [model: {caption.model_name}]"
        else:
            provider_note = f" [model: {caption.model_name}, provider: {caption.provider.value}]"
        return f"{caption.description.strip()}{provider_note}"

    def compose_bi_temporal_change(
        self,
        request: QueryRequest,
        change: BiTemporalChangeResult,
    ) -> str:
        parts: list[str] = []

        if change.scene_metrics and (
            change.scene_metrics.area_ha is not None or change.scene_metrics.area_m2 is not None
        ):
            if change.scene_metrics.area_ha is not None and change.scene_metrics.area_ha > 0:
                area_text = f"Detected approximately {change.scene_metrics.area_ha:g} ha of spectral change"
                if change.scene_metrics.changed_percentage is not None:
                    area_text += (
                        f", covering {change.scene_metrics.changed_percentage:g}% "
                        "of the analyzed area"
                    )
                parts.append(f"{area_text}.")
            elif change.scene_metrics.area_m2 is not None and change.scene_metrics.area_m2 > 0:
                parts.append(
                    f"Detected approximately {change.scene_metrics.area_m2:,.0f} m² of spectral change."
                )
        elif change.change_summary:
            parts.append(change.change_summary.strip().rstrip("."))

        if change.detector_summary and change.detector_summary.primary_index:
            index_label = change.detector_summary.primary_index.upper()
            signal_text = f"The primary signal was {index_label}"
            hint = change.detector_summary.change_direction_hint
            if hint and hint != "no_change":
                from app.evidence.bi_temporal_interpretation import humanize_direction_hint

                signal_text += (
                    f", with a direction hint consistent with {humanize_direction_hint(hint)}"
                )
            parts.append(f"{signal_text}.")

        if change.changed_region_count > 0:
            parts.append(
                f"{change.changed_region_count} mapped change region"
                f"{'s' if change.changed_region_count != 1 else ''} "
                f"between {change.earlier_date.isoformat()} and {change.later_date.isoformat()}."
            )
        elif not parts:
            parts.append(change.change_summary.strip())

        if change.detector_summary and change.detector_summary.histogram_confidence is not None:
            score = change.detector_summary.histogram_confidence
            parts.append(
                f"Histogram separability score: {score:.2f} "
                "(detector confidence, not model accuracy or event probability)."
            )

        if change.change_map_available:
            parts.append("Detected regions are shown on the map.")

        if not parts:
            parts.append(change.change_summary.strip())

        mode_note = " [development uploaded CVA — not Earth Engine catalog]"
        return " ".join(parts) + mode_note

    def compose_cross_modal(self, request: QueryRequest, result: CrossModalOpticalSARResult) -> str:
        mode_note = " [development cross-modal pipeline — not Earth Engine catalog fusion]"
        return f"{result.fused_analysis.summary.strip()}{mode_note}"

    def compose_building_temporal_policy(
        self,
        request: QueryRequest,
        report: ImageryPolicyReport,
    ) -> str:
        if report.policy_decision != PolicyDecision.SUPPORTED:
            return (
                report.reason_message
                or "Imagery policy does not support building-instance temporal analysis."
            )

        earlier = report.earlier
        later = report.later
        t1 = (
            f"T1 {earlier.sensor.value} ({earlier.gsd_m:g} m GSD)"
            if earlier
            else "T1 unknown"
        )
        t2 = (
            f"T2 {later.sensor.value} ({later.gsd_m:g} m GSD)"
            if later
            else "T2 unknown"
        )
        mismatch = (
            f"; resolution ratio {report.gsd_mismatch_ratio:.1f}×"
            if report.gsd_mismatch_ratio is not None
            else ""
        )
        return (
            f"Imagery policy supports building-instance temporal analysis for "
            f"{request.earlier_date.isoformat()} to {request.later_date.isoformat()} "
            f"({t1}, {t2}{mismatch}). "
            "Individual building segmentation and temporal matching are not yet implemented "
            "(Phase 5B); no building footprints or instance-level claims are produced."
        )
