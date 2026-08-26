"""FUTURE SatQuery integration boundary for a remote-sensing VLM (GeoChat).

STATUS: NOT WIRED INTO PRODUCTION. This module lives only in
experiments/phase9b_geochat_adaptation/ and is not imported by
backend/app/. It exists to define, review, and unit-test the eventual
interface shape BEFORE any integration work happens (Phase 9C+ decision).

Design mirrors the existing adapter pattern used throughout backend/app/adapters
(see e.g. app/adapters/semantic/base.py's `SemanticAnalyzer` ABC + factory):
  - an abstract base class with a `name` property and an async `analyze`
    method
  - a typed, observable-only result schema (no invented evidence metrics)
  - the caller (a future planner tool) remains responsible for choosing
    which specialist to invoke; the VLM never overrides CVA/Dynamic
    World/SAR measurements, it only adds VQA/captioning-style answers
    about a single image.

VLMResult intentionally contains ONLY things a model call can observe about
itself (answer text, optional confidence IF the model actually exposes one,
runtime, model identity, provenance). It must never contain a fabricated
change-area, confidence score invented outside the model's own logits, or
any field that could be mistaken for a specialist tool's measured evidence.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VLMTask(str, Enum):
    VQA = "vqa"
    CAPTIONING = "captioning"
    GROUNDING = "grounding"


class GroundingBox(BaseModel):
    """A model-reported bounding box, in the coordinate space of the INPUT
    image the model actually saw (pixel space), not geographic space.

    Mapping pixel-space boxes back to AOI geographic bounds (using the
    ImageInput's `bounds`/`crs`) is an explicit, separate, future
    transformation — never performed implicitly here, so this schema
    cannot be mistaken for a georeferenced geometry.
    """

    model_config = ConfigDict(extra="forbid")

    x_min: float
    y_min: float
    x_max: float
    y_max: float
    coordinate_space: str = Field(
        default="normalized_0_1_image_pixels",
        description="Always relative to the exact image the model was shown, never geographic.",
    )


class VLMResult(BaseModel):
    """Observable-only VLM output. See module docstring for the ground rule:
    no invented evidence metrics, no overriding specialist measurements.
    """

    model_config = ConfigDict(extra="forbid")

    task: VLMTask
    answer: str
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Only set if the underlying model actually exposes a "
        "calibrated confidence/probability; None otherwise (never guessed).",
    )
    grounding: GroundingBox | None = None
    model_name: str
    model_version: str
    input_image_ids: list[str]
    runtime_ms: int = Field(ge=0)
    provenance: str = Field(
        description="Free-text description of exactly which checkpoint/adapter "
        "produced this result (e.g. 'MBZUAI/geochat-7B base, no adapter' or "
        "'MBZUAI/geochat-7B + lora-bigearthnet-v1'). Never omitted."
    )


class RemoteSensingVLM(ABC):
    """Abstract interface a future GeoChat adapter would implement.

    Matches the existing SemanticAnalyzer/ImageryProvider/ChangeDetector
    adapter convention: a `name` identity property plus one narrow async
    entrypoint. A factory function (not implemented yet, deliberately —
    see README "SatQuery integration boundary") would select between a
    `DevelopmentVLM` (deterministic stub, explicitly labeled non-production)
    and a future `GeoChatVLM`, exactly like `get_semantic_analyzer()` does
    for SemanticAnalyzer today.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def supported_tasks(self) -> list[VLMTask]:
        ...

    @abstractmethod
    async def analyze(self, *, image_id: str, task: VLMTask, query: str) -> VLMResult:
        """Run one VLM call against one already-registered ImageInput.

        Implementations MUST NOT fabricate a VLMResult if the underlying
        model call fails — raise instead. There is no silent fallback to a
        canned answer, mirroring the existing adapters' explicit
        misconfiguration errors (see app/adapters/semantic/factory.py).
        """
        ...


# --- Planned (NOT implemented) routing table, documented for review only ---
#
# single-image VQA                 -> GeoChatVLM.analyze(task=VLMTask.VQA)
# single-image captioning/scene     -> GeoChatVLM.analyze(task=VLMTask.CAPTIONING)
# single-image grounding            -> GeoChatVLM.analyze(task=VLMTask.GROUNDING)
#                                      (grounding-capable specialist; see
#                                      Phase 9A grounding smoke-test notes)
# bi-temporal change reasoning      -> existing change specialist
#                                      (EarthEngineChangeDetector / CVA),
#                                      the VLM may be asked to DESCRIBE the
#                                      already-measured change region, never
#                                      to measure it itself
# optical + SAR paired analysis     -> existing multimodal_fusion.py;
#                                      VLM output (if any) is advisory
#                                      narrative only, fused evidence values
#                                      remain sourced from CVA/SAR/DW
#
# Concretely, wiring this in later (Phase 9C+, NOT done here) would mean,
# without changing any existing file's behavior:
#   1. app/adapters/rsvlm/base.py       - move this ABC there
#   2. app/adapters/rsvlm/factory.py    - get_rsvlm() keyed on a new
#                                          RSVLM=development|geochat setting,
#                                          same shape as
#                                          app/adapters/semantic/factory.py
#   3. app/tools/vlm/analyze_vqa.py     - a Tool[VLMInput, VLMResult]
#                                          subclass (app/tools/registry.py's
#                                          Tool ABC)
#   4. schemas/planning.py              - extend PlannerToolName /
#                                          QueryIntent + validators only if
#                                          VQA/captioning becomes a plannable
#                                          intent
#   5. TraceStep                        - reused as-is; model name/version
#                                          go in TraceStep.metadata, matching
#                                          how existing tools report
#                                          provenance
#   6. AnswerEngine                     - would consume VLMResult.answer only
#                                          as narrative text, never as a
#                                          measured metric (same rule it
#                                          already applies to SAR/semantic
#                                          evidence)
# None of steps 1-6 are performed in Phase 9B — this file documents the shape
# for review, per the task's explicit "do not modify the planner" instruction.
