#!/usr/bin/env python3
"""Run real GPU validation against a live GeoChat service and save local artifact."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_IMAGE = REPO_ROOT / "experiments" / "phase9b_geochat" / "assets" / "sentinel2_smoketest.png"
ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "validation_artifacts"
QUESTION = "Describe the main land-cover types visible in this satellite image."


def main() -> int:
    service_url = os.environ.get("GEOCHAT_SERVICE_URL")
    if not service_url:
        print("GEOCHAT_SERVICE_URL is required.", file=sys.stderr)
        return 1
    if not SMOKE_IMAGE.exists():
        print(f"Smoke image not found: {SMOKE_IMAGE}", file=sys.stderr)
        return 1

    health = httpx.get(f"{service_url.rstrip('/')}/health", timeout=30.0)
    health.raise_for_status()
    print(json.dumps(health.json(), indent=2))

    raw = SMOKE_IMAGE.read_bytes()
    payload = {
        "model_id": os.environ.get("GEOCHAT_MODEL_ID", "MBZUAI/geochat-7B"),
        "question": QUESTION,
        "image": {
            "content_base64": base64.b64encode(raw).decode("ascii"),
            "format": "png",
            "filename": SMOKE_IMAGE.name,
        },
        "image_metadata": {
            "image_id": "sentinel2-smoketest",
            "modality": "optical",
            "width": 504,
            "height": 504,
            "georeferenced": False,
            "benchmark_dataset": True,
        },
        "parameters": {"max_new_tokens": 200, "temperature": 1.0, "do_sample": False},
    }
    res = httpx.post(f"{service_url.rstrip('/')}/v1/vqa", json=payload, timeout=300.0)
    res.raise_for_status()
    body = res.json()
    if "development mock" in body.get("answer", "").lower():
        print("ERROR: response appears to be a development mock.", file=sys.stderr)
        return 2
    if body.get("model_name") != "MBZUAI/geochat-7B":
        print("ERROR: unexpected model_name.", file=sys.stderr)
        return 2

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = ARTIFACT_DIR / "real_gpu_smoke_vqa.json"
    artifact.write_text(json.dumps(body, indent=2))
    print(f"Saved artifact: {artifact}")
    print("ANSWER:", body.get("answer"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
