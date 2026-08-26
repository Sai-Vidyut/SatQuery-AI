#!/usr/bin/env python3
"""Phase 16 — real-world provider validation runner (validation only).

Requires GEOCHAT_SERVICE_URL for real GPU validations (P0).
Writes artifacts under services/geochat/validation_artifacts/ (gitignored).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = SERVICE_ROOT / "validation_artifacts"
SMOKE_PNG = REPO_ROOT / "experiments" / "phase9b_geochat" / "assets" / "sentinel2_smoketest.png"
SMOKE_META = REPO_ROOT / "experiments" / "phase9b_geochat" / "assets" / "sentinel2_smoketest.metadata.json"
VQA_QUESTION = "Describe the main land-cover types visible in this satellite image."
CAPTION_REQUEST = "Describe this satellite scene."
MODEL_ID = os.environ.get("GEOCHAT_MODEL_ID", "MBZUAI/geochat-7B")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _redact_service_url(url: str) -> str:
    """Safe identifier — host only, no credentials."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.hostname}:{parsed.port or ''}".rstrip(":")
    except Exception:
        return "<invalid-url>"


def build_georef_smoke_geotiff(out_path: Path) -> dict[str, Any]:
    """Create georeferenced GeoTIFF from real Sentinel-2 smoke PNG + metadata."""
    import numpy as np
    import tifffile
    from PIL import Image

    if not SMOKE_PNG.exists():
        raise FileNotFoundError(f"Smoke PNG missing: {SMOKE_PNG}")
    meta = json.loads(SMOKE_META.read_text()) if SMOKE_META.exists() else {}
    bounds = meta.get("aoi_wgs84", [16.546, 48.164, 16.654, 48.236])
    west, south, east, north = bounds
    img = Image.open(SMOKE_PNG).convert("RGB")
    width, height = img.size
    arr = np.asarray(img).transpose(2, 0, 1).astype(np.uint8)
    pixel_size_x = (east - west) / width
    pixel_size_y = (north - south) / height
    geokeys = (1, 1, 0, 1, 2048, 0, 1, 4326)
    extratags = [
        (33550, "d", 3, (pixel_size_x, pixel_size_y, 0.0), False),
        (33922, "d", 6, (0.0, 0.0, 0.0, west, north, 0.0), False),
        (34735, "H", len(geokeys), geokeys, False),
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(out_path, arr, extratags=extratags)
    return {
        "source": "sentinel2_smoketest.png",
        "metadata_file": str(SMOKE_META.relative_to(REPO_ROOT)),
        "label": meta.get("label", "REAL_SENTINEL2_SMOKETEST"),
        "scene_id": meta.get("scene_id"),
        "acquisition_time_iso": meta.get("acquisition_time_iso"),
        "bounds_wgs84": bounds,
        "width": width,
        "height": height,
        "output_path": str(out_path.resolve().relative_to(SERVICE_ROOT.resolve())),
    }


def validation_01_health(service_url: str) -> dict[str, Any]:
    res = httpx.get(f"{service_url.rstrip('/')}/health", timeout=60.0)
    body = res.json()
    _write_json(ARTIFACT_DIR / "real_health.json", body)
    ok = (
        res.status_code == 200
        and body.get("status") == "ok"
        and body.get("model_loaded") is True
        and body.get("model_name") == MODEL_ID
        and body.get("provider") == "geochat_service"
        and bool(body.get("gpu"))
    )
    return {
        "name": "validation_01_health",
        "passed": ok,
        "status_code": res.status_code,
        "body": body,
        "artifact": "validation_artifacts/real_health.json",
    }


def _image_payload() -> dict[str, Any]:
    raw = SMOKE_PNG.read_bytes()
    meta = json.loads(SMOKE_META.read_text()) if SMOKE_META.exists() else {}
    bounds = meta.get("aoi_wgs84")
    return {
        "content_base64": base64.b64encode(raw).decode("ascii"),
        "format": "png",
        "filename": SMOKE_PNG.name,
    }, {
        "image_id": "sentinel2-smoketest",
        "modality": "optical",
        "width": 504,
        "height": 504,
        "georeferenced": False,
        "benchmark_dataset": True,
        "acquisition_datetime": meta.get("acquisition_time_iso"),
        "bounds": bounds,
    }


def validation_02_direct_vqa(service_url: str) -> dict[str, Any]:
    image, image_metadata = _image_payload()
    payload = {
        "model_id": MODEL_ID,
        "question": VQA_QUESTION,
        "image": image,
        "image_metadata": image_metadata,
        "parameters": {"max_new_tokens": 200, "temperature": 1.0, "do_sample": False},
    }
    res = httpx.post(f"{service_url.rstrip('/')}/v1/vqa", json=payload, timeout=300.0)
    body = res.json()
    _write_json(ARTIFACT_DIR / "real_vqa.json", body)
    answer = body.get("answer", "")
    mock_markers = ("development mock", "[development mock")
    passed = (
        res.status_code == 200
        and bool(answer.strip())
        and body.get("provider") == "geochat_service"
        and body.get("model_name") == MODEL_ID
        and body.get("confidence_available") is False
        and not any(m in answer.lower() for m in mock_markers)
    )
    return {
        "name": "validation_02_direct_vqa",
        "passed": passed,
        "status_code": res.status_code,
        "answer_preview": answer[:500],
        "artifact": "validation_artifacts/real_vqa.json",
    }


def validation_04_caption(service_url: str) -> dict[str, Any]:
    image, image_metadata = _image_payload()
    payload = {
        "model_id": MODEL_ID,
        "user_request": CAPTION_REQUEST,
        "image": image,
        "image_metadata": image_metadata,
        "mode": "scene_description",
        "parameters": {"max_new_tokens": 200, "temperature": 1.0, "do_sample": False},
    }
    res = httpx.post(f"{service_url.rstrip('/')}/v1/caption", json=payload, timeout=300.0)
    body = res.json()
    _write_json(ARTIFACT_DIR / "real_caption.json", body)
    description = body.get("description", "")
    passed = (
        res.status_code == 200
        and bool(description.strip())
        and body.get("provider") == "geochat_service"
        and body.get("model_name") == MODEL_ID
        and body.get("confidence_available") is False
        and "development mock" not in description.lower()
    )
    return {
        "name": "validation_04_caption",
        "passed": passed,
        "status_code": res.status_code,
        "description_preview": description[:500],
        "artifact": "validation_artifacts/real_caption.json",
    }


def validation_03_backend_e2e(service_url: str, geotiff_path: Path) -> dict[str, Any]:
    """Run backend API against real GeoChat service (requires running backend)."""
    backend_url = os.environ.get("SATQUERY_BACKEND_URL", "http://127.0.0.1:8000")
    env = {
        **os.environ,
        "GEOCHAT_VQA_PROVIDER": "geochat_service",
        "GEOCHAT_SERVICE_URL": service_url,
        "GEOCHAT_MODEL_ID": MODEL_ID,
    }
    # Health check backend
    try:
        httpx.get(f"{backend_url.rstrip('/')}/api/v1/health", timeout=5.0)
    except httpx.HTTPError as exc:
        return {
            "name": "validation_03_backend_e2e",
            "passed": False,
            "skipped": True,
            "reason": f"Backend not reachable at {backend_url}: {exc}",
        }

    with geotiff_path.open("rb") as handle:
        up = httpx.post(
            f"{backend_url.rstrip('/')}/api/v1/imagery/upload",
            files={"file": (geotiff_path.name, handle, "image/tiff")},
            data={"modality": "optical"},
            timeout=60.0,
        )
    if up.status_code != 200:
        return {
            "name": "validation_03_backend_e2e",
            "passed": False,
            "upload_status": up.status_code,
            "upload_body": up.text[:500],
        }
    image_id = up.json()["data"]["image"]["id"]
    query = httpx.post(
        f"{backend_url.rstrip('/')}/api/v1/query/submit",
        json={"query": VQA_QUESTION, "image_id": image_id},
        timeout=300.0,
    )
    result_body = query.json()
    _write_json(ARTIFACT_DIR / "real_backend_vqa_result.json", result_body)
    trace = result_body.get("data", {}).get("trace", [])
    vqa_step = next((s for s in trace if s.get("step") == "geochat_vqa"), None)
    vqa = result_body.get("data", {}).get("result", {}).get("vqa", {})
    passed = (
        query.status_code == 200
        and vqa.get("provider") == "geochat_service"
        and vqa.get("model_name") == MODEL_ID
        and vqa_step is not None
        and "development mock" not in (vqa.get("answer") or "").lower()
    )
    return {
        "name": "validation_03_backend_e2e",
        "passed": passed,
        "image_id": image_id,
        "provider": vqa.get("provider"),
        "model": vqa.get("model_name"),
        "trace_steps": [s.get("step") for s in trace],
        "artifact": "validation_artifacts/real_backend_vqa_result.json",
        "env_note": "Backend must be started with GEOCHAT_VQA_PROVIDER=geochat_service",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-backend-e2e", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "phase": 16,
        "generated_at": _utc_now(),
        "model_id": MODEL_ID,
        "real_data_sources": {
            "sentinel2_smoketest_png": str(SMOKE_PNG.relative_to(REPO_ROOT)),
            "sentinel2_metadata": str(SMOKE_META.relative_to(REPO_ROOT)),
        },
        "validations": [],
        "blockers": [],
    }

    service_url = os.environ.get("GEOCHAT_SERVICE_URL")
    if not service_url:
        report["blockers"].append("GEOCHAT_SERVICE_URL not set — real GPU validations skipped.")
        _write_json(ARTIFACT_DIR / "phase16_runner_report.json", report)
        print(json.dumps(report, indent=2))
        return 2

    report["service_url_identifier"] = _redact_service_url(service_url)

    try:
        geotiff_info = build_georef_smoke_geotiff(ARTIFACT_DIR / "sentinel2_smoketest_georef.tif")
        report["georef_geotiff"] = geotiff_info
    except Exception as exc:
        report["blockers"].append(f"Could not build georef GeoTIFF: {exc}")
        _write_json(ARTIFACT_DIR / "phase16_runner_report.json", report)
        print(json.dumps(report, indent=2))
        return 1

    for fn in (validation_01_health, validation_02_direct_vqa, validation_04_caption):
        try:
            result = fn(service_url)
            report["validations"].append(result)
        except httpx.HTTPError as exc:
            report["validations"].append({"name": fn.__name__, "passed": False, "error": str(exc)})
            report["blockers"].append(f"{fn.__name__} failed: {exc}")

    if not args.skip_backend_e2e:
        report["validations"].append(
            validation_03_backend_e2e(service_url, ARTIFACT_DIR / "sentinel2_smoketest_georef.tif")
        )

    report["all_real_gpu_passed"] = all(v.get("passed") for v in report["validations"] if not v.get("skipped"))
    _write_json(ARTIFACT_DIR / "phase16_runner_report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["all_real_gpu_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
