#!/usr/bin/env python3
"""Deterministic conversion layer:

    BigEarthNet metadata/images
            v
    AdaptationExample (phase9b.bigearthnet)
            v
    GeoChat-compatible training record (LLaVA-style conversation JSON)

Only emits a training record for examples with image_available=True. This
is intentional: Phase 9B has not acquired raw BigEarthNet imagery (see
configs/dataset.yaml), so running this against the output of
prepare_bigearthnet_subset.py today will emit zero records, and the script
says so explicitly rather than emitting fake image paths.

Usage:
    python scripts/convert_to_geochat_format.py \
        --in data/bigearthnet_subset.jsonl \
        --out data/bigearthnet_geochat_train.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phase9b.bigearthnet import AdaptationExample  # noqa: E402


def to_llava_style_record(example: AdaptationExample, *, record_id: str) -> dict:
    """One AdaptationExample -> one LLaVA/GeoChat-style conversation record.

    Matches the conversation JSON shape GeoChat's own
    scripts/finetune_lora.sh training data loader expects:
    {"id": ..., "image": ..., "conversations": [{"from": "human", "value": "<image>\n<question>"}, {"from": "gpt", "value": "<answer>"}]}
    """
    if not example.image_available or example.image_path is None:
        raise ValueError(
            f"example {example.source_id} has no resolved image_path; "
            "cannot emit a training record from metadata alone"
        )
    return {
        "id": record_id,
        "image": example.image_path,
        "conversations": [
            {"from": "human", "value": f"<image>\n{example.question}"},
            {"from": "gpt", "value": example.reference_answer},
        ],
        "source_dataset": "bigearthnet_txt",
        "source_id": example.source_id,
        "task_type": example.task_type,
        "category": example.category,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_path", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    examples = []
    with args.in_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(AdaptationExample.model_validate(json.loads(line)))

    trainable = [e for e in examples if e.image_available]
    skipped = len(examples) - len(trainable)

    records = [
        to_llava_style_record(e, record_id=f"ben_{e.source_id}") for e in trainable
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(records, indent=2))

    print(f"[convert] read {len(examples)} examples, {len(trainable)} trainable, {skipped} skipped (no image)")
    print(f"[convert] wrote {len(records)} training records to {args.out}")
    if len(records) == 0:
        print(
            "[convert] NOTE: 0 trainable records. Raw BigEarthNet imagery has "
            "not been acquired in Phase 9B — see configs/dataset.yaml. This "
            "is expected, not an error."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
