"""Render evaluation records as markdown reports."""

from __future__ import annotations

from evaluation.models import EvaluationRecord


def render_markdown_report(records: list[EvaluationRecord]) -> str:
    lines = ["# SatQuery Phase 6 Evaluation Report", ""]
    for record in records:
        lines.append(f"## {record.case_id} ({record.domain})")
        lines.append(f"- **Status:** {record.status}")
        lines.append(f"- **Evaluation type:** {record.evaluation_type.value}")
        lines.append(f"- **Provider / mode:** {record.imagery_provider} / {record.data_mode}")
        lines.append(f"- **Planner intent:** {record.planner_intent}")
        lines.append(f"- **Change domain:** {record.change_domain}")
        lines.append(f"- **Regions:** {record.region_count} (candidates: {record.candidate_region_count})")
        lines.append(f"- **Changed area (m²):** {record.changed_area_m2}")
        lines.append(f"- **Confidence:** {record.confidence}")
        lines.append(f"- **Total time (ms):** {record.total_duration_ms}")
        if record.answer_mentions_development_mock:
            lines.append("- **WARNING:** Answer contains development/mock disclaimer")
        if record.error_code:
            lines.append(f"- **Error:** {record.error_code} — {record.error_message}")
        if record.quantitative:
            q = record.quantitative
            lines.append(
                f"- **Metrics:** IoU={q.iou} P={q.precision} R={q.recall} F1={q.f1}"
            )
        if record.answer:
            lines.append(f"- **Answer excerpt:** {record.answer[:240]}…")
        lines.append("")
    return "\n".join(lines)
