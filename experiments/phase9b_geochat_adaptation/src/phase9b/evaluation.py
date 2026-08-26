"""Evaluation plan scaffolding for single-image VQA / captioning / grounding.

This module defines the INTERFACE and file formats for evaluation. It does
NOT compute or claim any benchmark score — no benchmark data has been
downloaded or run in Phase 9B (see README "Evaluation plan").
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PredictionRecord(BaseModel):
    """One model prediction, saved as a single JSON line (JSONL) per example.

    This is the ONLY format predictions should be written in, so a later
    evaluation script can be written once and reused across VRSBench/RSVQA/
    CDVQA without bespoke parsing per dataset.
    """

    model_config = ConfigDict(extra="forbid")

    example_id: str
    dataset: str  # e.g. "bigearthnet_txt", "rsvqa", "vrsbench", "cdvqa", "real_sentinel2_smoketest"
    task: str  # "vqa" | "captioning" | "grounding" | "change_vqa"
    question: str
    reference_answer: str | None = None  # None when no ground truth exists (e.g. smoke test)
    model_answer: str
    model_name: str
    model_version: str
    runtime_ms: int = Field(ge=0)


def write_predictions_jsonl(records: list[PredictionRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")


def read_predictions_jsonl(path: Path) -> list[PredictionRecord]:
    records: list[PredictionRecord] = []
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(PredictionRecord.model_validate(json.loads(line)))
    return records


class EvaluationMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: float
    num_examples: int
    task: str
    dataset: str


# --- Evaluation plan (interfaces only — not executed against benchmark data) ---
#
# 1. single-image VQA (binary/MCQ, e.g. BigEarthNet.txt `type=binary/mcq`,
#    RSVQA): exact-match accuracy on normalized (lowercased, stripped)
#    answer strings. metric = "accuracy".
#
# 2. captioning (e.g. VRSBench captioning split): BLEU-4 / ROUGE-L / CIDEr
#    via a standard library (e.g. `pycocoevalcap` or `evaluate`), computed
#    from PredictionRecord.model_answer vs reference_answer. metric names =
#    "bleu4", "rougeL", "cider".
#
# 3. grounding (e.g. VRSBench grounding split): IoU between the model's
#    GroundingBox (see vlm_interface.py) and the reference box, thresholded
#    at IoU>=0.5 for "grounding accuracy" (standard detection-style metric).
#
# 4. multitemporal change understanding (CDVQA): same exact-match accuracy
#    as (1), but the VLM is given a DESCRIPTION of the already-measured
#    change region (from the existing change specialist) rather than being
#    asked to measure change itself — consistent with vlm_interface.py's
#    routing table.
#
# 5. optical+SAR paired analysis: no established single metric; plan is a
#    qualitative rubric (coherence, hallucination rate against known
#    fused-evidence facts) scored by manual review in the first pass, not
#    an automated metric, since no such VLM benchmark is in scope here.
#
# All metrics will be computed by a future evaluate.py CLI (not built in
# Phase 9B) that: reads a PredictionRecord JSONL, groups by (dataset, task),
# computes the metric above, and writes a list[EvaluationMetric] to
# outputs/eval_<dataset>_<task>.json. This keeps evaluation fully
# reproducible from saved predictions without re-running the model.
