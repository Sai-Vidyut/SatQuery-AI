"""Run catalog evaluation cases through the production query controller."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.config import get_settings
from app.schemas.change_domain import DOMAIN_CLAIM_TYPES, ChangeDomain
from app.schemas.domain import QueryRequest
from app.services.query_controller import QueryController
from evaluation.metrics import compute_region_metrics
from evaluation.models import EvaluationCase, EvaluationRecord, EvaluationType, StepTiming


CASES_DIR = Path(__file__).resolve().parent / "cases"


def load_cases(path: Path | None = None) -> list[EvaluationCase]:
    case_path = path or (CASES_DIR / "catalog_cases.json")
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    return [EvaluationCase.model_validate(item) for item in payload["cases"]]


def _region_area_total(regions) -> float:
    total = 0.0
    for region in regions:
        for metric in region.metrics:
            if metric.name in {"area_m2", "estimated_area", "area_km2"}:
                value = float(metric.value)
                total += value * 1_000_000 if metric.name == "area_km2" else value
    return total


def _extract_fetch_metadata(result) -> dict[str, Any]:
    fetch_step = next((s for s in result.trace if s.tool_name == "fetch_imagery"), None)
    if fetch_step and fetch_step.metadata:
        return dict(fetch_step.metadata)
    return {}


def _extract_scenes(result) -> list[dict[str, Any]]:
    fetch_meta = _extract_fetch_metadata(result)
    scenes = fetch_meta.get("scenes")
    if isinstance(scenes, list):
        return scenes
    return []


class EvaluationRunner:
    """Execute evaluation cases and produce structured records."""

    def __init__(self, controller: QueryController | None = None) -> None:
        self._controller = controller or QueryController()

    async def run_case(self, case: EvaluationCase) -> EvaluationRecord:
        settings = get_settings()
        t0 = perf_counter()
        request = QueryRequest(
            query=case.query,
            aoi=case.aoi,
            earlier_date=case.earlier_date,
            later_date=case.later_date,
        )
        try:
            result = await self._controller.submit(request)
        except Exception as exc:
            code = getattr(exc, "code", "evaluation_failed")
            message = getattr(exc, "message", str(exc))
            return EvaluationRecord(
                case_id=case.case_id,
                domain=case.domain,
                evaluation_type=case.evaluation_type,
                status="failed",
                error_code=code,
                error_message=message,
                imagery_provider=settings.imagery_provider,
                total_duration_ms=int((perf_counter() - t0) * 1000),
            )

        plan_step = next((s for s in result.trace if s.tool_name == "plan_query"), None)
        plan_meta = (plan_step.metadata or {}) if plan_step else {}
        detect_step = next((s for s in result.trace if s.tool_name == "detect_change"), None)
        detect_meta = (detect_step.metadata or {}) if detect_step else {}
        fetch_meta = _extract_fetch_metadata(result)

        domain_enum = ChangeDomain(case.domain) if case.domain in ChangeDomain._value2member_map_ else None
        claim_type = DOMAIN_CLAIM_TYPES.get(domain_enum) if domain_enum else None
        candidate_count = (
            sum(1 for r in result.evidence if r.metadata.get("claim_type") == claim_type)
            if claim_type
            else 0
        )

        t1_meta = fetch_meta.get("t1") if isinstance(fetch_meta.get("t1"), dict) else None
        t2_meta = fetch_meta.get("t2") if isinstance(fetch_meta.get("t2"), dict) else None
        fallback_events = fetch_meta.get("fallback_events")
        if not isinstance(fallback_events, list):
            fallback_events = []

        record = EvaluationRecord(
            case_id=case.case_id,
            domain=case.domain,
            evaluation_type=case.evaluation_type,
            status="completed",
            imagery_provider=settings.imagery_provider,
            data_mode=result.mode.value,
            detector=detect_meta.get("detector"),
            scenes=_extract_scenes(result),
            planner_intent=plan_meta.get("intent"),
            change_domain=plan_meta.get("change_domain"),
            required_tools=plan_meta.get("required_tools") or [],
            region_count=len(result.evidence),
            candidate_region_count=candidate_count,
            changed_area_m2=_region_area_total(result.evidence) or detect_meta.get("area_m2"),
            confidence=result.confidence,
            answer=result.answer,
            answer_mentions_development_mock=(
                "demonstration data" in (result.answer or "").lower()
                or result.demonstration_data
            ),
            step_timings=[
                StepTiming(
                    tool_name=step.tool_name,
                    duration_ms=step.duration_ms,
                    status=step.status.value if step.status else None,
                )
                for step in result.trace
            ],
            total_duration_ms=int((perf_counter() - t0) * 1000),
            detector_metadata=detect_meta if isinstance(detect_meta, dict) else {},
            composite_provenance={
                "t1": fetch_meta.get("t1"),
                "t2": fetch_meta.get("t2"),
                "imagery_strategy": fetch_meta.get("imagery_strategy"),
                "composite_method": fetch_meta.get("composite_method"),
                "fallback_events": fallback_events,
                "fallback_policy": fetch_meta.get("fallback_policy"),
            },
            imagery_strategy=fetch_meta.get("imagery_strategy"),
            requested_earlier_date=case.earlier_date,
            requested_later_date=case.later_date,
            actual_t1_window=t1_meta,
            actual_t2_window=t2_meta,
            fallback_events=fallback_events,
            confidence_semantics=detect_meta.get("confidence_kind") or "histogram_separability",
            demonstration_data=result.demonstration_data,
            trace_summary=[
                {
                    "tool_name": step.tool_name,
                    "status": step.status.value if step.status else None,
                    "duration_ms": step.duration_ms,
                    "summary": step.summary,
                }
                for step in result.trace
            ],
            qualitative_assessment={
                "detected_regions": len(result.evidence) > 0,
                "has_domain_candidates": candidate_count > 0,
                "expected_change": case.expected_change,
                "reference": case.reference,
            },
        )

        if (
            case.evaluation_type == EvaluationType.QUANTITATIVE
            and case.ground_truth is not None
            and result.evidence
        ):
            record.quantitative = compute_region_metrics(
                result.evidence,
                case.ground_truth.geometry,
            )

        return record

    async def run_all(self, cases: list[EvaluationCase] | None = None) -> list[EvaluationRecord]:
        items = cases or load_cases()
        records: list[EvaluationRecord] = []
        for case in items:
            records.append(await self.run_case(case))
        return records


def records_to_json(records: list[EvaluationRecord]) -> str:
    return json.dumps([r.model_dump(mode="json") for r in records], indent=2)
