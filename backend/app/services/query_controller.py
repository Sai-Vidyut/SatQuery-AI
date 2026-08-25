from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import perf_counter

from app.core.errors import SatQueryError
from app.evidence.engine import EvidenceEngine
from app.schemas.domain import (
    AnalysisResult,
    AnalysisStatus,
    ChangeDetectionInput,
    DetectSARChangeInput,
    FetchImageryInput,
    FuseEvidenceInput,
    GenerateEvidenceInput,
    ImageryRequest,
    QueryRequest,
    SemanticAnalysisInput,
    SensorType,
    TraceStatus,
    TraceStep,
)
from app.schemas.planning import QueryAnalysisPlan, SensorRequirement
from app.services.answer_engine import AnswerEngine
from app.services.planner.service import plan_query
from app.services.session_store import SessionStore, session_store
from app.tools.evidence.fuse_evidence import FuseEvidenceTool
from app.tools.evidence.generate_evidence import GenerateEvidenceTool
from app.tools.imagery.fetch_imagery import FetchImageryTool
from app.tools.semantic.analyze_semantics import AnalyzeSemanticsTool
from app.tools.temporal.detect_change import DetectChangeTool
from app.tools.temporal.detect_sar_change import DetectSARChangeTool


class QueryController:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or session_store
        self._fetch = FetchImageryTool()
        self._detect = DetectChangeTool()
        self._detect_sar = DetectSARChangeTool()
        self._semantic = AnalyzeSemanticsTool()
        self._fuse = FuseEvidenceTool()
        self._evidence_tool = GenerateEvidenceTool()
        self._evidence = EvidenceEngine()
        self._answer = AnswerEngine()

    async def submit(self, request: QueryRequest) -> AnalysisResult:
        session_id = self._store.create()
        trace: list[TraceStep] = []
        plan_output = await self._run_plan_step(trace, request)
        plan = plan_output.plan

        try:
            imagery_out = await self._run_step(
                trace,
                "fetch_imagery",
                self._fetch_imagery(request, plan),
            )
            detections = await self._run_step(
                trace,
                "detect_change",
                self._detect_change(request, imagery_out),
            )
            semantic_out = await self._run_semantics_step(
                trace,
                request,
                imagery_out,
                detections,
                plan,
            )
            sar_out = await self._run_sar_step(trace, request, plan, detections)
            cva_detections = (
                detections
                if request.sensor != SensorType.SENTINEL_1
                else detections.model_copy(update={"regions": [], "raw_detection_count": 0})
            )
            sar_detections = sar_out if request.sensor != SensorType.SENTINEL_1 else detections
            fused_out = await self._run_step(
                trace,
                "fuse_evidence",
                self._fuse_evidence(cva_detections, semantic_out, sar_detections),
            )
            evidence_out = await self._run_step(
                trace,
                "generate_evidence",
                self._generate_evidence(request, imagery_out, fused_out),
            )

            metrics = self._evidence.aggregate_metrics(
                evidence_out.metrics,
                cva_detections if request.sensor != SensorType.SENTINEL_1 else detections,
                semantic_out,
                sar_detections if sar_detections and sar_detections.raw_detection_count else None,
                fused_out.fusion_metadata,
            )
            answer = self._answer.compose(
                request,
                evidence_out,
                imagery_out.result.mode,
                analysis_profile=plan.profile,
                fusion_metadata=fused_out.fusion_metadata,
            )

            result = AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                session_id=session_id,
                answer=answer,
                confidence=evidence_out.confidence,
                metrics=metrics,
                evidence=evidence_out.regions,
                trace=trace,
                mode=imagery_out.result.mode,
            )
            self._store.complete(session_id, result)
            return result
        except SatQueryError:
            raise
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise SatQueryError("analysis_failed", str(exc), status_code=500) from exc

    def get_trace(self, session_id: str) -> list[TraceStep]:
        session = self._store.get(session_id)
        if not session:
            raise SatQueryError("session_not_found", f"No session: {session_id}", status_code=404)
        return session.trace

    def get_result(self, session_id: str) -> AnalysisResult:
        session = self._store.get(session_id)
        if not session or not session.result:
            raise SatQueryError("session_not_found", f"No result for session: {session_id}", status_code=404)
        return session.result

    async def _run_plan_step(self, trace: list[TraceStep], request: QueryRequest):
        step_id = f"plan_query-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="plan_query",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Planning analysis route…",
        )
        trace.append(step)
        await asyncio.sleep(0)

        try:
            plan_output = await plan_query(request)
            elapsed = int((perf_counter() - t0) * 1000)
            plan = plan_output.plan
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = (
                f"planner={plan_output.planner} intent={plan.user_intent.value} "
                f"tools={','.join(t.value for t in plan.required_tools)}"
            )
            step.metadata = {
                "planner": plan_output.planner,
                "intent": plan.user_intent.value,
                "required_tools": [t.value for t in plan.required_tools],
                "requested_modalities": [m.value for m in plan.requested_modalities],
                "planner_version": plan.planner_version,
                "fallback_used": plan_output.fallback_used,
                "status": TraceStatus.COMPLETED.value,
                "duration_ms": elapsed,
            }
            return plan_output
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.error = str(exc)
            step.summary = "plan_query failed"
            raise

    async def _run_semantics_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        imagery_out,
        detections,
        plan: QueryAnalysisPlan,
    ):
        if not plan.run_semantic or request.sensor == SensorType.SENTINEL_1:
            return self._record_skipped_step(trace, "analyze_semantics", "not required by analysis plan")

        return await self._run_step(
            trace,
            "analyze_semantics",
            self._analyze_semantics(request, imagery_out, detections, plan.profile),
        )

    async def _run_sar_step(self, trace: list[TraceStep], request: QueryRequest, plan: QueryAnalysisPlan, detections):
        if request.sensor == SensorType.SENTINEL_1:
            return self._record_skipped_step(
                trace,
                "detect_sar_change",
                "SAR-only query uses detect_change results",
            )
        if not plan.run_sar:
            return self._record_skipped_step(trace, "detect_sar_change", "not required by analysis plan")
        return await self._run_step(trace, "detect_sar_change", self._detect_sar_change(request))

    def _record_skipped_step(self, trace: list[TraceStep], tool_name: str, reason: str):
        step = TraceStep(
            id=f"{tool_name}-{len(trace) + 1}",
            tool_name=tool_name,
            status=TraceStatus.COMPLETED,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=0,
            summary=f"{tool_name} skipped ({reason})",
        )
        trace.append(step)
        return None

    async def _run_step(self, trace: list[TraceStep], tool_name: str, coro):
        step_id = f"{tool_name}-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name=tool_name,
            status=TraceStatus.RUNNING,
            started_at=started,
            summary=f"Running {tool_name}…",
        )
        trace.append(step)
        await asyncio.sleep(0.05)

        try:
            output = await coro
            elapsed = int((perf_counter() - t0) * 1000)
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = self._summarize(tool_name, output)
            return output
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.error = str(exc)
            step.summary = f"{tool_name} failed"
            raise

    def _summarize(self, tool_name: str, output) -> str:
        if tool_name == "plan_query":
            return "Analysis plan validated"
        if tool_name == "fetch_imagery":
            return f"Acquired {len(output.result.scenes)} scene(s) via {output.result.source}"
        if tool_name == "detect_change":
            detector = getattr(output, "detector", "unknown")
            return f"Detected {output.raw_detection_count} region(s) via {detector}"
        if tool_name == "detect_sar_change":
            detector = getattr(output, "detector", "unknown")
            return f"Detected {output.raw_detection_count} SAR region(s) via {detector}"
        if tool_name == "analyze_semantics":
            return f"Produced {len(output.regions)} semantic region(s) via {output.analyzer}"
        if tool_name == "fuse_evidence":
            return f"Fused {len(output.regions)} evidence region(s) ({output.fusion_metadata.get('fusion_policy')})"
        if tool_name == "generate_evidence":
            return f"Validated {len(output.regions)} evidence region(s)"
        return f"{tool_name} completed"

    async def _fetch_imagery(self, request: QueryRequest, plan: QueryAnalysisPlan):
        if plan.sensor_requirement == SensorRequirement.SENTINEL_1:
            sensor = SensorType.SENTINEL_1
        elif plan.sensor_requirement == SensorRequirement.SENTINEL_2:
            sensor = SensorType.SENTINEL_2
        else:
            sensor = SensorType.SENTINEL_2
        imagery_request = ImageryRequest(
            aoi=request.aoi,
            start_date=request.earlier_date,
            end_date=request.later_date,
            sensor=sensor,
            preferences=request.preferences,
        )
        return await self._fetch.execute(FetchImageryInput(request=imagery_request))

    async def _detect_change(self, request: QueryRequest, fetch_output):
        payload = ChangeDetectionInput(
            aoi=request.aoi,
            earlier_date=request.earlier_date,
            later_date=request.later_date,
            imagery=fetch_output.result,
        )
        return await self._detect.execute(payload)

    async def _detect_sar_change(self, request: QueryRequest):
        return await self._detect_sar.execute(
            DetectSARChangeInput(
                aoi=request.aoi,
                earlier_date=request.earlier_date,
                later_date=request.later_date,
                preferences=request.preferences,
            )
        )

    async def _analyze_semantics(self, request, fetch_output, detections, analysis_profile: str | None):
        payload = SemanticAnalysisInput(
            aoi=request.aoi,
            earlier_date=request.earlier_date,
            later_date=request.later_date,
            imagery=fetch_output.result,
            change_regions=detections.regions,
            analysis_profile=analysis_profile or "building_construction",
        )
        return await self._semantic.execute(payload)

    async def _fuse_evidence(self, detections, semantic_output, sar_output):
        return await self._fuse.execute(
            FuseEvidenceInput(
                cva_detections=detections,
                semantic=semantic_output,
                sar_detections=sar_output,
            )
        )

    async def _generate_evidence(self, request, imagery_output, fused_output):
        return await self._evidence_tool.execute(
            GenerateEvidenceInput(
                query=request.query,
                imagery=imagery_output.result,
                fused_regions=fused_output.regions,
                fusion_metadata=fused_output.fusion_metadata,
            )
        )

    def _fail_trace(self, trace: list[TraceStep], exc: Exception) -> None:
        if trace and trace[-1].status == TraceStatus.RUNNING:
            trace[-1].status = TraceStatus.FAILED
            trace[-1].error = str(exc)


query_controller = QueryController()
