from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import perf_counter

from app.adapters.change.factory import get_upload_change_detector
from app.adapters.imagery.uploaded.bi_temporal_bridge import build_change_detection_input
from app.adapters.imagery.uploaded.cross_modal_bridge import (
    build_cross_modal_imagery_result,
    pair_bounds,
)
from app.adapters.imagery.uploaded.compatibility import (
    resolve_co_registration_status,
    validate_bi_temporal,
    validate_optical_sar_pair,
    validate_single_image,
)
from app.adapters.imagery.uploaded.factory import get_uploaded_imagery_provider
from app.core.errors import SatQueryError
from app.evidence.engine import EvidenceEngine
from app.schemas.domain import (
    AnalysisResult,
    AnalysisStatus,
    ChangeDetectionInput,
    DataMode,
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
from app.schemas.change_understanding import ChangeUnderstandingToolInput
from app.schemas.input import ImageInput, ImageModality, InputValidationResult
from app.schemas.planning import QueryAnalysisPlan, QueryIntent, SensorRequirement
from app.schemas.imagery_policy import ImageryProductMode, PolicyDecision, TemporalImageryResolution
from app.schemas.vqa import (
    GeoChatCaptionInput,
    GeoChatCaptionParameters,
    GeoChatVQAInput,
    GeoChatVQAParameters,
)
from app.services.answer_engine import AnswerEngine
from app.services.planner.service import plan_query
from app.services.session_store import SessionStore, session_store
from app.services.temporal_imagery_resolver import TemporalImageryResolver
from app.services.change_domain import annotate_regions_for_domain, domain_metrics_from_regions
from app.schemas.cross_modal import (
    CrossModalFusionInput,
    OpticalAnalysisInput,
    SARAnalysisInput,
)
from app.services.cross_modal_pipeline import build_cross_modal_metrics, build_cross_modal_result
from app.tools.single_image.geochat_caption import GeoChatCaptionTool
from app.tools.single_image.geochat_vqa import GeoChatVQATool
from app.tools.evidence.fuse_evidence import FuseEvidenceTool
from app.tools.evidence.generate_evidence import GenerateEvidenceTool
from app.tools.imagery.fetch_imagery import FetchImageryTool
from app.tools.semantic.analyze_semantics import AnalyzeSemanticsTool
from app.tools.temporal.detect_change import DetectChangeTool
from app.tools.temporal.detect_sar_change import DetectSARChangeTool
from app.services.vqa_pipeline import build_caption_metrics, build_vqa_metrics
from app.tools.temporal.change_understanding import ChangeUnderstandingTool
from app.tools.cross_modal.cross_modal_fusion import CrossModalFusionTool
from app.tools.cross_modal.optical_analysis import UploadedOpticalAnalysisTool
from app.tools.cross_modal.sar_analysis import UploadedSARAnalysisTool


class QueryController:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or session_store
        self._fetch = FetchImageryTool()
        self._detect = DetectChangeTool()
        self._upload_detect = DetectChangeTool(detector=get_upload_change_detector())
        self._detect_sar = DetectSARChangeTool()
        self._semantic = AnalyzeSemanticsTool()
        self._fuse = FuseEvidenceTool()
        self._evidence_tool = GenerateEvidenceTool()
        self._evidence = EvidenceEngine()
        self._answer = AnswerEngine()
        self._geochat_vqa = GeoChatVQATool()
        self._geochat_caption = GeoChatCaptionTool()
        self._change_understanding = ChangeUnderstandingTool()
        self._optical_analysis = UploadedOpticalAnalysisTool()
        self._sar_analysis = UploadedSARAnalysisTool()
        self._cross_modal_fusion = CrossModalFusionTool()
        self._imagery_resolver = TemporalImageryResolver()

    async def submit(self, request: QueryRequest) -> AnalysisResult:
        if request.is_cross_modal_upload:
            return await self._submit_cross_modal_optical_sar(request)
        if request.is_bi_temporal_upload:
            return await self._submit_bi_temporal_change(request)
        if request.is_single_image_vqa:
            return await self._submit_single_image(request)
        return await self._submit_temporal_analysis(request)

    async def _submit_cross_modal_optical_sar(self, request: QueryRequest) -> AnalysisResult:
        session_id = self._store.create()
        trace: list[TraceStep] = []
        optical_id = request.optical_image_id
        sar_id = request.sar_image_id
        if not optical_id or not sar_id:
            raise SatQueryError(
                "invalid_request",
                "optical_image_id and sar_image_id are required for cross-modal analysis.",
                status_code=400,
            )

        try:
            provider = get_uploaded_imagery_provider()
            for image_id in (optical_id, sar_id):
                if not provider.exists(image_id):
                    raise SatQueryError(
                        "image_not_found",
                        f"Unknown image_id: {image_id}",
                        status_code=404,
                    )
            optical = provider.get(optical_id)
            sar = provider.get(sar_id)

            validation = await self._run_cross_modal_validation_step(trace, optical, sar)
            if not validation.valid:
                self._store.update_trace(session_id, trace)
                raise SatQueryError(
                    "input_validation_failed",
                    "; ".join(validation.errors) or "Cross-modal input validation failed.",
                    status_code=400,
                )

            plan_output = await self._run_plan_step(trace, request)
            plan = plan_output.plan
            if plan.user_intent != QueryIntent.CROSS_MODAL_OPTICAL_SAR:
                raise SatQueryError(
                    "planner_routing_error",
                    f"Expected cross_modal_optical_sar intent, got {plan.user_intent.value}.",
                    status_code=500,
                )

            bounds = pair_bounds(optical, sar)
            co_registration_status, co_registration_provenance = resolve_co_registration_status(
                optical, sar
            )

            optical_summary = await self._run_optical_analysis_step(
                trace, request, optical, bounds, plan
            )
            sar_summary = await self._run_sar_analysis_step(trace, request, sar, bounds, plan)
            fused_summary, fused_regions = await self._run_cross_modal_fusion_step(
                trace,
                request,
                optical,
                sar,
                optical_summary,
                sar_summary,
                bounds,
                co_registration_status,
                plan,
            )
            evidence_out = await self._run_cross_modal_generate_evidence_step(
                trace,
                request,
                optical,
                sar,
                fused_regions,
            )

            cross_modal_result = build_cross_modal_result(
                request,
                optical=optical_summary,
                sar=sar_summary,
                fused=fused_summary,
                co_registration_status=co_registration_status,
                co_registration_provenance=co_registration_provenance,
                optical_image_id=optical_id,
                sar_image_id=sar_id,
                fused_regions_count=len(fused_regions),
            )
            answer = self._answer.compose_cross_modal(request, cross_modal_result)
            metrics = build_cross_modal_metrics(cross_modal_result) + evidence_out.metrics

            result = AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                session_id=session_id,
                answer=answer,
                confidence=0.0,
                confidence_available=False,
                metrics=metrics,
                evidence=evidence_out.regions,
                trace=trace,
                mode=DataMode.DEVELOPMENT,
                cross_modal=cross_modal_result,
            )
            self._store.complete(session_id, result)
            return result
        except SatQueryError:
            raise
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise SatQueryError("analysis_failed", str(exc), status_code=500) from exc

    async def _submit_bi_temporal_change(self, request: QueryRequest) -> AnalysisResult:
        session_id = self._store.create()
        trace: list[TraceStep] = []
        earlier_id = request.earlier_image_id
        later_id = request.later_image_id
        if not earlier_id or not later_id:
            raise SatQueryError(
                "invalid_request",
                "earlier_image_id and later_image_id are required for bi-temporal change analysis.",
                status_code=400,
            )

        try:
            provider = get_uploaded_imagery_provider()
            for image_id in (earlier_id, later_id):
                if not provider.exists(image_id):
                    raise SatQueryError(
                        "image_not_found",
                        f"Unknown image_id: {image_id}",
                        status_code=404,
                    )
            earlier = provider.get(earlier_id)
            later = provider.get(later_id)

            validation = await self._run_bi_temporal_validation_step(trace, earlier, later)
            if not validation.valid:
                self._store.update_trace(session_id, trace)
                raise SatQueryError(
                    "input_validation_failed",
                    "; ".join(validation.errors) or "Bi-temporal input validation failed.",
                    status_code=400,
                )

            plan_output = await self._run_plan_step(trace, request)
            plan = plan_output.plan
            if plan.user_intent != QueryIntent.BI_TEMPORAL_CHANGE_VQA:
                raise SatQueryError(
                    "planner_routing_error",
                    f"Expected bi_temporal_change_vqa intent, got {plan.user_intent.value}.",
                    status_code=500,
                )

            detections = await self._run_uploaded_detect_change_step(trace, request, earlier, later, plan)
            detector_meta = detections.detector_metadata or {}
            from app.evidence.bi_temporal_interpretation import (
                enrich_region_metadata,
                metrics_from_detector_metadata,
            )

            regions = [
                r.model_copy(
                    update={
                        "metadata": enrich_region_metadata(
                            r,
                            detector=detections.detector,
                            detector_metadata=detector_meta,
                        )
                    }
                )
                for r in detections.regions
            ]
            if plan.change_domain:
                regions = annotate_regions_for_domain(
                    regions,
                    plan.change_domain,
                    direction_hint=detector_meta.get("change_direction_hint"),
                    primary_index=detector_meta.get("primary_index"),
                )
            understanding = await self._run_change_understanding_step(
                trace, request, earlier, later, detections, plan
            )
            evidence_out = await self._run_bi_temporal_generate_evidence_step(
                trace,
                request,
                detections,
                regions,
                earlier=earlier,
                later=later,
            )

            answer = self._answer.compose_bi_temporal_change(
                request,
                understanding.result,
                change_domain=plan.change_domain,
            )
            confidence = (
                understanding.result.confidence
                if understanding.result.confidence_available
                else evidence_out.confidence
            )
            detector_metrics = metrics_from_detector_metadata(
                detector_meta,
                source=detections.detector,
            )
            existing_metric_names = {metric.name for metric in evidence_out.metrics}
            merged_metrics = evidence_out.metrics + [
                metric for metric in detector_metrics if metric.name not in existing_metric_names
            ]
            if plan.change_domain:
                domain_metrics = domain_metrics_from_regions(
                    plan.change_domain,
                    evidence_out.regions,
                    detector_meta,
                )
                existing_metric_names = {metric.name for metric in merged_metrics}
                merged_metrics.extend(
                    metric for metric in domain_metrics if metric.name not in existing_metric_names
                )
            result = AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                session_id=session_id,
                answer=answer,
                confidence=confidence,
                confidence_available=understanding.result.confidence_available or bool(regions),
                metrics=merged_metrics,
                evidence=evidence_out.regions,
                trace=trace,
                mode=DataMode.DEVELOPMENT,
                bi_temporal_change=understanding.result,
            )
            self._store.complete(session_id, result)
            return result
        except SatQueryError:
            raise
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise SatQueryError("analysis_failed", str(exc), status_code=500) from exc

    async def _submit_single_image(self, request: QueryRequest) -> AnalysisResult:
        session_id = self._store.create()
        trace: list[TraceStep] = []
        image_id = request.image_id
        if not image_id:
            raise SatQueryError(
                "invalid_request",
                "image_id is required for single-image VQA or scene caption.",
                status_code=400,
            )

        try:
            provider = get_uploaded_imagery_provider()
            if not provider.exists(image_id):
                raise SatQueryError("image_not_found", f"Unknown image_id: {image_id}", status_code=404)
            image = provider.get(image_id)

            validation = await self._run_input_validation_step(trace, image)
            if not validation.valid:
                self._store.update_trace(session_id, trace)
                raise SatQueryError(
                    "input_validation_failed",
                    "; ".join(validation.errors) or "Input validation failed.",
                    status_code=400,
                )

            plan_output = await self._run_plan_step(trace, request, image_modality=image.modality)
            plan = plan_output.plan
            if plan.user_intent == QueryIntent.SINGLE_IMAGE_CAPTION:
                caption_out = await self._run_geochat_caption_step(trace, request, image, plan)
                await self._run_caption_generate_evidence_step(trace, caption_out.result)

                answer = self._answer.compose_caption(request, caption_out.result)
                metrics = build_caption_metrics(caption_out.result)
                mode = (
                    DataMode.EARTH_ENGINE
                    if caption_out.result.provider.value == "geochat_service"
                    else DataMode.DEVELOPMENT
                )
                confidence = (
                    caption_out.result.confidence if caption_out.result.confidence_available else 0.0
                )
                result = AnalysisResult(
                    status=AnalysisStatus.COMPLETED,
                    session_id=session_id,
                    answer=answer,
                    confidence=confidence,
                    confidence_available=caption_out.result.confidence_available,
                    metrics=metrics,
                    evidence=[],
                    trace=trace,
                    mode=mode,
                    caption=caption_out.result,
                )
                self._store.complete(session_id, result)
                return result

            if plan.user_intent != QueryIntent.SINGLE_IMAGE_VQA:
                raise SatQueryError(
                    "planner_routing_error",
                    f"Expected single_image_vqa or single_image_caption intent, got {plan.user_intent.value}.",
                    status_code=500,
                )

            vqa_out = await self._run_geochat_vqa_step(trace, request, image, plan)
            await self._run_vqa_generate_evidence_step(trace, vqa_out.result)

            answer = self._answer.compose_vqa(request, vqa_out.result)
            metrics = build_vqa_metrics(vqa_out.result)
            mode = (
                DataMode.EARTH_ENGINE
                if vqa_out.result.provider.value == "geochat_service"
                else DataMode.DEVELOPMENT
            )
            confidence = vqa_out.result.confidence if vqa_out.result.confidence_available else 0.0
            result = AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                session_id=session_id,
                answer=answer,
                confidence=confidence,
                confidence_available=vqa_out.result.confidence_available,
                metrics=metrics,
                evidence=[],
                trace=trace,
                mode=mode,
                vqa=vqa_out.result,
            )
            self._store.complete(session_id, result)
            return result
        except SatQueryError:
            raise
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise SatQueryError("analysis_failed", str(exc), status_code=500) from exc

    async def _submit_temporal_analysis(self, request: QueryRequest) -> AnalysisResult:
        session_id = self._store.create()
        trace: list[TraceStep] = []
        plan_output = await self._run_plan_step(trace, request)
        plan = plan_output.plan

        if plan.user_intent == QueryIntent.BUILDING_TEMPORAL_CHANGE:
            return await self._submit_building_temporal_policy(session_id, trace, request)

        try:
            imagery_out = await self._run_step(
                trace,
                "fetch_imagery",
                self._fetch_imagery(request, plan),
            )
            detections = await self._run_step(
                trace,
                "detect_change",
                self._detect_change(request, imagery_out, plan),
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

            evidence_regions = list(evidence_out.regions)
            if plan.change_domain:
                semantic_regions = semantic_out.regions if semantic_out else []
                sar_regions = sar_detections.regions if sar_detections else []
                evidence_regions = annotate_regions_for_domain(
                    evidence_regions,
                    plan.change_domain,
                    direction_hint=(detections.detector_metadata or {}).get("change_direction_hint"),
                    primary_index=(detections.detector_metadata or {}).get("primary_index"),
                    has_semantic_built=bool(semantic_regions),
                    has_sar_support=bool(sar_regions),
                )
                evidence_out = evidence_out.model_copy(update={"regions": evidence_regions})

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
                change_domain=plan.change_domain,
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
                demonstration_data=request.demo_mode or imagery_out.result.mode == DataMode.DEVELOPMENT,
            )
            self._store.complete(session_id, result)
            return result
        except SatQueryError:
            raise
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise SatQueryError("analysis_failed", str(exc), status_code=500) from exc

    async def _submit_building_temporal_policy(
        self,
        session_id: str,
        trace: list[TraceStep],
        request: QueryRequest,
    ) -> AnalysisResult:
        try:
            resolution = await self._run_imagery_policy_step(trace, request)
            report = resolution.report
            self._store.update_trace(session_id, trace)
            if report.policy_decision == PolicyDecision.UNSUPPORTED:
                raise SatQueryError(
                    "imagery_policy_unsupported",
                    report.reason_message
                    or "Imagery policy does not support building-instance temporal analysis.",
                    status_code=422,
                )
            answer = self._answer.compose_building_temporal_policy(request, report)
            result = AnalysisResult(
                status=AnalysisStatus.COMPLETED,
                session_id=session_id,
                answer=answer,
                confidence=0.0,
                confidence_available=False,
                metrics=[],
                evidence=[],
                trace=trace,
                mode=DataMode.DEVELOPMENT,
                imagery_policy=report,
            )
            self._store.complete(session_id, result)
            return result
        except SatQueryError:
            raise
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise SatQueryError("analysis_failed", str(exc), status_code=500) from exc

    async def _run_imagery_policy_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
    ) -> TemporalImageryResolution:
        step_id = f"imagery_policy-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="imagery_policy",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Evaluating imagery suitability for building-instance temporal analysis…",
        )
        trace.append(step)
        await asyncio.sleep(0)

        resolution = self._imagery_resolver.resolve_catalog(
            request.aoi,
            request.earlier_date,
            request.later_date,
            ImageryProductMode.BUILDING_INSTANCE,
        )
        report = resolution.report
        elapsed = int((perf_counter() - t0) * 1000)
        step.status = TraceStatus.COMPLETED
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        step.summary = (
            f"policy={report.policy_decision.value}"
            + (f" reason={report.reason_code}" if report.reason_code else "")
        )
        step.metadata = {
            "requested_mode": ImageryProductMode.BUILDING_INSTANCE.value,
            "t1_sensor": report.earlier.sensor.value if report.earlier else None,
            "t2_sensor": report.later.sensor.value if report.later else None,
            "t1_gsd_m": report.earlier.gsd_m if report.earlier else None,
            "t2_gsd_m": report.later.gsd_m if report.later else None,
            "t1_requested_date": (
                report.earlier.requested_date.isoformat() if report.earlier else None
            ),
            "t2_requested_date": (
                report.later.requested_date.isoformat() if report.later else None
            ),
            "t1_actual_acquisition_date": (
                report.earlier.actual_acquisition_date.isoformat()
                if report.earlier and report.earlier.actual_acquisition_date
                else None
            ),
            "t2_actual_acquisition_date": (
                report.later.actual_acquisition_date.isoformat()
                if report.later and report.later.actual_acquisition_date
                else None
            ),
            "policy_decision": report.policy_decision.value,
            "reason_code": report.reason_code,
            "gsd_mismatch_ratio": report.gsd_mismatch_ratio,
            "warnings": report.warnings,
            "status": TraceStatus.COMPLETED.value,
            "duration_ms": elapsed,
        }
        return resolution

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

    async def _run_plan_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        *,
        image_modality: ImageModality | None = None,
    ):
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
            plan_output = await plan_query(request, image_modality=image_modality)
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
                "change_domain": plan.change_domain.value if plan.change_domain else None,
                "required_tools": [t.value for t in plan.required_tools],
                "requested_modalities": [m.value for m in plan.requested_modalities],
                "planner_version": plan.planner_version,
                "fallback_used": plan_output.fallback_used,
                "demo_mode": request.demo_mode,
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

    async def _run_input_validation_step(
        self,
        trace: list[TraceStep],
        image: ImageInput,
    ) -> InputValidationResult:
        step_id = f"input_validation-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="input_validation",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Validating uploaded image input…",
        )
        trace.append(step)
        await asyncio.sleep(0)
        validation = validate_single_image(image)
        elapsed = int((perf_counter() - t0) * 1000)
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        if validation.valid:
            step.status = TraceStatus.COMPLETED
            step.summary = "Input validation passed."
        else:
            step.status = TraceStatus.FAILED
            step.summary = "Input validation failed."
            step.error = "; ".join(validation.errors)
        step.metadata = {
            "task": "single_image",
            "image_id": image.id,
            "modality": image.modality.value,
            "format": image.format.value,
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "checks": [c.model_dump() for c in validation.checks],
            "status": step.status.value,
            "duration_ms": elapsed,
        }
        return validation

    async def _run_bi_temporal_validation_step(
        self,
        trace: list[TraceStep],
        earlier: ImageInput,
        later: ImageInput,
    ) -> InputValidationResult:
        step_id = f"input_validation-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="input_validation",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Validating uploaded bi-temporal image pair…",
        )
        trace.append(step)
        await asyncio.sleep(0)
        validation = validate_bi_temporal(earlier, later, require_acquisition_dates=True)
        elapsed = int((perf_counter() - t0) * 1000)
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        if validation.valid:
            step.status = TraceStatus.COMPLETED
            step.summary = "Bi-temporal input validation passed."
        else:
            step.status = TraceStatus.FAILED
            step.summary = "Bi-temporal input validation failed."
            step.error = "; ".join(validation.errors)
        step.metadata = {
            "task": "bi_temporal_change_vqa",
            "earlier_image_id": earlier.id,
            "later_image_id": later.id,
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "checks": [c.model_dump() for c in validation.checks],
            "status": step.status.value,
            "duration_ms": elapsed,
        }
        return validation

    async def _run_uploaded_detect_change_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        earlier: ImageInput,
        later: ImageInput,
        plan: QueryAnalysisPlan,
    ):
        step_id = f"detect_change-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="detect_change",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Running change detection on uploaded bi-temporal pair…",
            metadata={
                "task": plan.user_intent.value,
                "detector": get_upload_change_detector().name,
                "earlier_image_id": earlier.id,
                "later_image_id": later.id,
            },
        )
        trace.append(step)
        await asyncio.sleep(0)
        try:
            payload = build_change_detection_input(earlier, later, query_hint=request.query)
            output = await self._upload_detect.execute(payload)
            elapsed = int((perf_counter() - t0) * 1000)
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = (
                f"Detected {output.raw_detection_count} change region(s) via {output.detector}"
            )
            step.metadata = {
                **(step.metadata or {}),
                "provider": "uploaded_bi_temporal",
                "detector": output.detector,
                "raw_detection_count": output.raw_detection_count,
                "status": TraceStatus.COMPLETED.value,
                "duration_ms": elapsed,
            }
            if output.detector_metadata.get("pipeline_stages"):
                step.metadata["pipeline_stages"] = output.detector_metadata["pipeline_stages"]
            for key in (
                "primary_index",
                "histogram_confidence",
                "confidence_kind",
                "change_direction_hint",
                "area_ha",
                "changed_percentage",
                "region_count",
            ):
                value = output.detector_metadata.get(key)
                if value is not None:
                    step.metadata[key] = value
            return output
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = int((perf_counter() - t0) * 1000)
            if isinstance(exc, SatQueryError):
                step.error = exc.message
                step.metadata = {
                    **(step.metadata or {}),
                    "error_code": exc.code,
                    "status": TraceStatus.FAILED.value,
                    "duration_ms": step.duration_ms,
                }
            else:
                step.error = str(exc)
            from app.adapters.change.bi_temporal.errors import BiTemporalPipelineError

            if isinstance(exc, BiTemporalPipelineError) and exc.pipeline_stages:
                step.metadata = {
                    **(step.metadata or {}),
                    "pipeline_stages": exc.pipeline_stages,
                }
            step.summary = "detect_change failed"
            raise

    async def _run_change_understanding_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        earlier: ImageInput,
        later: ImageInput,
        detections,
        plan: QueryAnalysisPlan,
    ):
        step_id = f"change_understanding-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="change_understanding",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Interpreting change evidence for the user question…",
            metadata={
                "task": plan.user_intent.value,
                "question": request.query,
                "detector": detections.detector,
            },
        )
        trace.append(step)
        await asyncio.sleep(0)
        try:
            output = await self._change_understanding.execute(
                ChangeUnderstandingToolInput(
                    query=request.query,
                    earlier=earlier,
                    later=later,
                    detections=detections,
                    change_domain=plan.change_domain,
                )
            )
            elapsed = int((perf_counter() - t0) * 1000)
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = (
                f"Change understanding completed ({output.result.changed_region_count} regions)"
            )
            step.metadata = {
                **(step.metadata or {}),
                "provider": output.result.provider.value,
                "detector": output.result.detector,
                "changed_region_count": output.result.changed_region_count,
                "change_map_available": output.result.change_map_available,
                "confidence_kind": output.result.confidence_kind,
                "status": TraceStatus.COMPLETED.value,
                "duration_ms": elapsed,
            }
            if output.result.detector_summary:
                summary = output.result.detector_summary
                step.metadata.update(
                    {
                        "primary_index": summary.primary_index,
                        "change_direction_hint": summary.change_direction_hint,
                        "histogram_confidence": summary.histogram_confidence,
                    }
                )
            if output.result.scene_metrics:
                scene = output.result.scene_metrics
                step.metadata.update(
                    {
                        "area_ha": scene.area_ha,
                        "changed_percentage": scene.changed_percentage,
                        "region_count": scene.region_count,
                    }
                )
            return output
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.error = str(exc)
            step.summary = "change_understanding failed"
            raise

    async def _run_bi_temporal_generate_evidence_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        detections,
        regions,
        *,
        earlier: ImageInput,
        later: ImageInput,
    ):
        step_id = f"generate_evidence-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="generate_evidence",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Packaging bi-temporal change evidence…",
        )
        trace.append(step)
        await asyncio.sleep(0)
        from app.adapters.imagery.uploaded.bi_temporal_bridge import build_imagery_result_from_pair

        imagery = build_imagery_result_from_pair(earlier, later)
        evidence_out = await self._evidence_tool.execute(
            GenerateEvidenceInput(
                query=request.query,
                imagery=imagery,
                fused_regions=regions,
                fusion_metadata={
                    "source": "uploaded_bi_temporal_cva",
                    "detector_metadata": detections.detector_metadata or {},
                },
            )
        )
        elapsed = int((perf_counter() - t0) * 1000)
        step.status = TraceStatus.COMPLETED
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        step.summary = f"Validated {len(evidence_out.regions)} change evidence region(s)."
        step.metadata = {
            "task": "bi_temporal_change_vqa",
            "evidence_regions": len(evidence_out.regions),
            "detector": detections.detector,
            "status": TraceStatus.COMPLETED.value,
            "duration_ms": elapsed,
        }
        detector_meta = detections.detector_metadata or {}
        for key in ("primary_index", "histogram_confidence", "area_ha", "changed_percentage"):
            value = detector_meta.get(key)
            if value is not None:
                step.metadata[key] = value
        return evidence_out

    async def _run_cross_modal_validation_step(
        self,
        trace: list[TraceStep],
        optical: ImageInput,
        sar: ImageInput,
    ) -> InputValidationResult:
        step_id = f"input_validation-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="input_validation",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Validating uploaded optical+SAR cross-modal pair…",
        )
        trace.append(step)
        await asyncio.sleep(0)
        validation = validate_optical_sar_pair(optical, sar)
        coreg_status, coreg_msg = resolve_co_registration_status(optical, sar)
        elapsed = int((perf_counter() - t0) * 1000)
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        if validation.valid:
            step.status = TraceStatus.COMPLETED
            step.summary = "Cross-modal input validation passed."
        else:
            step.status = TraceStatus.FAILED
            step.summary = "Cross-modal input validation failed."
            step.error = "; ".join(validation.errors)
        step.metadata = {
            "task": "cross_modal_optical_sar",
            "optical_image_id": optical.id,
            "sar_image_id": sar.id,
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "co_registration_status": coreg_status.value,
            "co_registration_provenance": coreg_msg,
            "checks": [c.model_dump() for c in validation.checks],
            "status": step.status.value,
            "duration_ms": elapsed,
        }
        return validation

    async def _run_optical_analysis_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        optical: ImageInput,
        bounds: list[float],
        plan: QueryAnalysisPlan,
    ):
        step_id = f"optical_analysis-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="optical_analysis",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Running optical/multispectral specialist…",
            metadata={"task": plan.user_intent.value, "optical_image_id": optical.id},
        )
        trace.append(step)
        await asyncio.sleep(0)
        try:
            summary = await self._optical_analysis.execute(
                OpticalAnalysisInput(
                    query=request.query,
                    optical_image_id=optical.id,
                    bounds=bounds,
                )
            )
            elapsed = int((perf_counter() - t0) * 1000)
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = f"Optical analysis completed ({len(summary.regions)} region cues)"
            step.metadata = {
                **(step.metadata or {}),
                "analyzer": summary.analyzer,
                "provider": summary.provider.value,
                "region_count": len(summary.regions),
                "status": TraceStatus.COMPLETED.value,
                "duration_ms": elapsed,
            }
            return summary
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.error = str(exc)
            step.summary = "optical_analysis failed"
            raise

    async def _run_sar_analysis_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        sar: ImageInput,
        bounds: list[float],
        plan: QueryAnalysisPlan,
    ):
        step_id = f"sar_analysis-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="sar_analysis",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Running SAR specialist…",
            metadata={"task": plan.user_intent.value, "sar_image_id": sar.id},
        )
        trace.append(step)
        await asyncio.sleep(0)
        try:
            summary = await self._sar_analysis.execute(
                SARAnalysisInput(
                    query=request.query,
                    sar_image_id=sar.id,
                    bounds=bounds,
                )
            )
            elapsed = int((perf_counter() - t0) * 1000)
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = f"SAR analysis completed ({len(summary.regions)} region cues)"
            step.metadata = {
                **(step.metadata or {}),
                "analyzer": summary.analyzer,
                "provider": summary.provider.value,
                "region_count": len(summary.regions),
                "status": TraceStatus.COMPLETED.value,
                "duration_ms": elapsed,
            }
            return summary
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.error = str(exc)
            step.summary = "sar_analysis failed"
            raise

    async def _run_cross_modal_fusion_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        optical: ImageInput,
        sar: ImageInput,
        optical_summary,
        sar_summary,
        bounds: list[float],
        co_registration_status,
        plan: QueryAnalysisPlan,
    ):
        step_id = f"cross_modal_fusion-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="cross_modal_fusion",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Fusing optical and SAR analyses…",
            metadata={
                "task": plan.user_intent.value,
                "optical_image_id": optical.id,
                "sar_image_id": sar.id,
                "co_registration_status": co_registration_status.value,
            },
        )
        trace.append(step)
        await asyncio.sleep(0)
        try:
            fused_summary, fused_regions = await self._cross_modal_fusion.execute(
                CrossModalFusionInput(
                    query=request.query,
                    optical=optical_summary,
                    sar=sar_summary,
                    optical_image_id=optical.id,
                    sar_image_id=sar.id,
                    bounds=bounds,
                    co_registration_status=co_registration_status,
                )
            )
            elapsed = int((perf_counter() - t0) * 1000)
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = (
                f"Cross-modal fusion produced {fused_summary.fused_region_count} joint region(s)"
            )
            step.metadata = {
                **(step.metadata or {}),
                "fusion_policy": fused_summary.fusion_policy,
                "fused_region_count": fused_summary.fused_region_count,
                "status": TraceStatus.COMPLETED.value,
                "duration_ms": elapsed,
            }
            return fused_summary, fused_regions
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.error = str(exc)
            step.summary = "cross_modal_fusion failed"
            raise

    async def _run_cross_modal_generate_evidence_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        optical: ImageInput,
        sar: ImageInput,
        fused_regions,
    ):
        step_id = f"generate_evidence-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="generate_evidence",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Packaging cross-modal fused evidence…",
        )
        trace.append(step)
        await asyncio.sleep(0)
        imagery = build_cross_modal_imagery_result(optical, sar)
        evidence_out = await self._evidence_tool.execute(
            GenerateEvidenceInput(
                query=request.query,
                imagery=imagery,
                fused_regions=fused_regions,
                fusion_metadata={"source": "uploaded_cross_modal_fusion"},
            )
        )
        elapsed = int((perf_counter() - t0) * 1000)
        step.status = TraceStatus.COMPLETED
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        step.summary = f"Validated {len(evidence_out.regions)} fused evidence region(s)."
        step.metadata = {
            "task": "cross_modal_optical_sar",
            "evidence_regions": len(evidence_out.regions),
            "status": TraceStatus.COMPLETED.value,
            "duration_ms": elapsed,
        }
        return evidence_out

    async def _run_geochat_vqa_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        image: ImageInput,
        plan: QueryAnalysisPlan,
    ):
        step_id = f"geochat_vqa-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        parameters = GeoChatVQAParameters()
        step = TraceStep(
            id=step_id,
            tool_name="geochat_vqa",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Running GeoChat single-image VQA…",
            metadata={
                "task": plan.user_intent.value,
                "model": "MBZUAI/geochat-7B",
                "requested_modality": plan.requested_modalities[0].value,
                "parameters": parameters.model_dump(),
            },
        )
        trace.append(step)
        await asyncio.sleep(0)
        try:
            output = await self._geochat_vqa.execute(
                GeoChatVQAInput(image=image, question=request.query, parameters=parameters)
            )
            elapsed = int((perf_counter() - t0) * 1000)
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = (
                f"GeoChat VQA completed via {output.result.provider.value} "
                f"({output.result.model_name})"
            )
            step.metadata = {
                **(step.metadata or {}),
                "provider": output.result.provider.value,
                "model_name": output.result.model_name,
                "model_version": output.result.model_version,
                "provenance": output.result.provenance,
                "confidence_available": output.result.confidence_available,
                "status": TraceStatus.COMPLETED.value,
                "duration_ms": elapsed,
                "fallback_used": False,
            }
            return output
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.error = str(exc)
            step.summary = "geochat_vqa failed"
            raise

    async def _run_geochat_caption_step(
        self,
        trace: list[TraceStep],
        request: QueryRequest,
        image: ImageInput,
        plan: QueryAnalysisPlan,
    ):
        step_id = f"geochat_caption-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        parameters = GeoChatCaptionParameters()
        step = TraceStep(
            id=step_id,
            tool_name="geochat_caption",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Running GeoChat single-image scene description…",
            metadata={
                "task": plan.user_intent.value,
                "model": "MBZUAI/geochat-7B",
                "requested_modality": plan.requested_modalities[0].value,
                "parameters": parameters.model_dump(),
            },
        )
        trace.append(step)
        await asyncio.sleep(0)
        try:
            output = await self._geochat_caption.execute(
                GeoChatCaptionInput(
                    image=image,
                    user_request=request.query,
                    parameters=parameters,
                )
            )
            elapsed = int((perf_counter() - t0) * 1000)
            step.status = TraceStatus.COMPLETED
            step.completed_at = datetime.now(UTC)
            step.duration_ms = elapsed
            step.summary = (
                f"GeoChat scene caption completed via {output.result.provider.value} "
                f"({output.result.model_name})"
            )
            step.metadata = {
                **(step.metadata or {}),
                "provider": output.result.provider.value,
                "model_name": output.result.model_name,
                "model_version": output.result.model_version,
                "provenance": output.result.provenance,
                "confidence_available": output.result.confidence_available,
                "status": TraceStatus.COMPLETED.value,
                "duration_ms": elapsed,
                "fallback_used": False,
            }
            return output
        except Exception as exc:
            step.status = TraceStatus.FAILED
            step.completed_at = datetime.now(UTC)
            step.error = str(exc)
            step.summary = "geochat_caption failed"
            raise

    async def _run_caption_generate_evidence_step(self, trace: list[TraceStep], caption_result) -> None:
        step_id = f"generate_evidence-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="generate_evidence",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Packaging scene-description provenance…",
        )
        trace.append(step)
        await asyncio.sleep(0)
        elapsed = int((perf_counter() - t0) * 1000)
        step.status = TraceStatus.COMPLETED
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        step.summary = "Scene description and provenance recorded (no spatial evidence regions)."
        step.metadata = {
            "task": "single_image_caption",
            "evidence_regions": 0,
            "model_name": caption_result.model_name,
            "provider": caption_result.provider.value,
            "provenance": caption_result.provenance,
            "status": TraceStatus.COMPLETED.value,
            "duration_ms": elapsed,
        }

    async def _run_vqa_generate_evidence_step(self, trace: list[TraceStep], vqa_result) -> None:
        step_id = f"generate_evidence-{len(trace) + 1}"
        started = datetime.now(UTC)
        t0 = perf_counter()
        step = TraceStep(
            id=step_id,
            tool_name="generate_evidence",
            status=TraceStatus.RUNNING,
            started_at=started,
            summary="Packaging VQA provenance and answer…",
        )
        trace.append(step)
        await asyncio.sleep(0)
        elapsed = int((perf_counter() - t0) * 1000)
        step.status = TraceStatus.COMPLETED
        step.completed_at = datetime.now(UTC)
        step.duration_ms = elapsed
        step.summary = "VQA answer and provenance recorded (no spatial evidence regions)."
        step.metadata = {
            "task": "single_image_vqa",
            "evidence_regions": 0,
            "model_name": vqa_result.model_name,
            "provider": vqa_result.provider.value,
            "provenance": vqa_result.provenance,
            "status": TraceStatus.COMPLETED.value,
            "duration_ms": elapsed,
        }

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
            meta = self._step_metadata(tool_name, output)
            if meta:
                step.metadata = meta
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
            strategy = (output.result.provider_metadata or {}).get("imagery_strategy")
            if strategy == "seasonal_median_composite":
                t1 = (output.result.provider_metadata or {}).get("t1", {})
                t2 = (output.result.provider_metadata or {}).get("t2", {})
                return (
                    f"Built median composites: T1 {t1.get('scene_count', '?')} scenes "
                    f"({t1.get('window_start', '?')}–{t1.get('window_end', '?')}), "
                    f"T2 {t2.get('scene_count', '?')} scenes "
                    f"({t2.get('window_start', '?')}–{t2.get('window_end', '?')})"
                )
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
        if tool_name == "geochat_vqa":
            return f"GeoChat VQA via {output.result.provider.value}"
        if tool_name == "geochat_caption":
            return f"GeoChat scene caption via {output.result.provider.value}"
        if tool_name == "change_understanding":
            return f"Change understanding via {output.result.detector}"
        return f"{tool_name} completed"

    def _step_metadata(self, tool_name: str, output) -> dict[str, object] | None:
        if tool_name == "fetch_imagery":
            result = output.result
            provider_meta = result.provider_metadata or {}
            scenes_meta = []
            for scene in result.scenes:
                scene_entry: dict[str, object] = {
                    "scene_id": scene.scene_id,
                    "acquisition_date": scene.acquisition_date.isoformat(),
                    "platform_id": scene.platform_id,
                    "cloud_cover_percent": scene.cloud_cover_percent,
                }
                if scene.metadata:
                    strategy = scene.metadata.get("imagery_strategy")
                    if strategy:
                        scene_entry["imagery_strategy"] = strategy
                        scene_entry["composite_method"] = scene.metadata.get("composite_method")
                        scene_entry["window_start"] = scene.metadata.get("window_start")
                        scene_entry["window_end"] = scene.metadata.get("window_end")
                        scene_entry["scene_count"] = scene.metadata.get("scene_count")
                scenes_meta.append(scene_entry)
            return {
                "provider": result.source,
                "data_mode": result.mode.value,
                "sensor": result.sensor.value,
                "scene_count": len(result.scenes),
                "scenes": scenes_meta,
                "selection_policy": provider_meta.get("selection_policy"),
                "imagery_strategy": provider_meta.get("imagery_strategy"),
                "composite_method": provider_meta.get("composite_method"),
                "t1": provider_meta.get("t1"),
                "t2": provider_meta.get("t2"),
                "seasonality": provider_meta.get("seasonality"),
                "fallback_events": provider_meta.get("fallback_events"),
                "fallback_policy": provider_meta.get("fallback_policy"),
                "demonstration_data": provider_meta.get("demonstration_data", False),
            }
        if tool_name == "detect_change":
            metadata = output.detector_metadata or {}
            return {
                "detector": output.detector,
                "data_mode": output.mode.value,
                "raw_detection_count": output.raw_detection_count,
                "region_count": len(output.regions),
                "detector_version": metadata.get("detector_version"),
                "method": metadata.get("method"),
                "threshold": metadata.get("threshold"),
                "primary_index": metadata.get("primary_index"),
                "change_direction_hint": metadata.get("change_direction_hint"),
                "seasonality_warnings": metadata.get("seasonality_warnings"),
                "confidence_kind": metadata.get("confidence_kind") or "histogram_separability",
                "area_ha": metadata.get("area_ha"),
                "area_m2": metadata.get("area_m2"),
                "changed_percentage": metadata.get("changed_percentage"),
            }
        return None

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
            demo_mode=request.demo_mode,
        )
        return await self._fetch.execute(FetchImageryInput(request=imagery_request))

    async def _detect_change(self, request: QueryRequest, fetch_output, plan: QueryAnalysisPlan):
        payload = ChangeDetectionInput(
            aoi=request.aoi,
            earlier_date=request.earlier_date,
            later_date=request.later_date,
            imagery=fetch_output.result,
            query_hint=request.query,
            change_domain=plan.change_domain.value if plan.change_domain else None,
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
            code = getattr(exc, "code", "analysis_failed")
            trace[-1].metadata = {
                **(trace[-1].metadata or {}),
                "error_code": code,
                "status": TraceStatus.FAILED.value,
            }


query_controller = QueryController()
