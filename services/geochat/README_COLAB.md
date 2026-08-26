# GeoChat Service — Google Colab T4 Validation

Temporary Colab launcher for **real** `MBZUAI/geochat-7B` inference via the existing `services/geochat` FastAPI service.

This path is for **Phase 16 validation only**. It does **not** start the SatQuery backend and does **not** use the development mock provider.

## What this runs

```
Colab T4  -->  services/geochat (FastAPI :8080)  -->  MBZUAI/geochat-7B
```

Your local SatQuery backend connects over HTTP:

```bash
export GEOCHAT_VQA_PROVIDER=geochat_service
export GEOCHAT_SERVICE_URL=http://<colab-public-url>:8080
```

## Prerequisites

1. **Google Colab** with **T4 GPU** runtime (`Runtime` → `Change runtime type` → `T4 GPU`)
2. Clone this repository in Colab:

```python
!git clone https://github.com/Sai-Vidyut/SatQuery-AI.git /content/SatQuery-AI
```

3. **Optional:** Hugging Face token if your environment requires authenticated downloads:

```python
import os
os.environ["HF_TOKEN"] = "hf_..."  # never commit; Colab secret recommended
```

The launcher reads `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` from the environment only.

## Quick start

**Cell 1 — start the service** (blocks while running; first start downloads weights):

```python
!bash /content/SatQuery-AI/services/geochat/scripts/colab_start.sh
```

**Cell 2 — health check** (open a new cell while Cell 1 is running):

```bash
curl http://127.0.0.1:8080/health
```

Expected response fields:

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_name": "MBZUAI/geochat-7B",
  "gpu": "Tesla T4",
  "provider": "geochat_service",
  "load_strategy": "geochat_upstream_8bit_device_map_auto_deferred_clip504"
}
```

## What the launcher installs

Only what `services/geochat` needs:

| Component | Source |
|-----------|--------|
| FastAPI, uvicorn, pydantic, pillow, numpy, tifffile | `pip install -e services/geochat` |
| transformers 4.36.2, accelerate, bitsandbytes, sentencepiece, einops | Phase 9B pinned Colab stack |
| torch | **Colab pre-installed** (not reinstalled) |
| GeoChat upstream source | `git clone` to `/content/geochat` |
| SatQuery backend | **Not installed** |

Model weights (`MBZUAI/geochat-7B`) are **not** downloaded during `pip install`. They load when uvicorn starts (`GEOCHAT_EAGER_LOAD=true`).

## Verified loading strategy

Implemented in `geochat_service/inference.py` (same as Phase 9B Colab smoke test):

- `load_in_8bit=True`
- `device_map="auto"`
- `low_cpu_mem_usage=True`
- Deferred CLIP 336→504 interpolation after checkpoint load
- `geochat_service.patches.apply_geochat_patches()` on cloned GeoChat repo

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEOCHAT_SRC` | `/content/geochat` | Cloned GeoChat upstream repo |
| `GEOCHAT_MODEL_ID` | `MBZUAI/geochat-7B` | Hugging Face model id |
| `GEOCHAT_EAGER_LOAD` | `true` | Load model on service startup |
| `GEOCHAT_SERVICE_HOST` | `0.0.0.0` | Bind address |
| `GEOCHAT_SERVICE_PORT` | `8080` | Listen port |
| `HF_TOKEN` | — | Optional Hugging Face auth |

`GEOCHAT_SERVICE_FAKE_ENGINE` is explicitly **unset** by the launcher.

## Connecting from your machine

Colab `127.0.0.1` is only reachable inside the notebook. To validate from a local SatQuery backend, expose port 8080 (e.g. Colab's port forwarding, `ngrok`, or Cloudflare tunnel) and set:

```bash
export GEOCHAT_SERVICE_URL=http://<public-host>:8080
export GEOCHAT_REAL_SERVICE_TEST=true
cd backend && uv run python ../services/geochat/scripts/run_phase16_validation.py
```

## Validation artifacts

Save results to `services/geochat/validation_artifacts/` (gitignored) per `docs/SIH_PHASE16_VALIDATION.md`.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| `CUDA is not available` | Switch Colab runtime to T4 GPU |
| `GEOCHAT_SRC does not contain geochat package` | Re-run launcher (clone step failed) |
| `bitsandbytes failed CUDA initialization` | Restart runtime; re-run launcher |
| Health shows `model_loaded: false` | Wait for first-time HF download; check `HF_TOKEN` if auth required |
| OOM on T4 | Restart runtime; ensure no other GPU processes |

## What this does NOT do

- Does not start `backend/` or the SatQuery API
- Does not use `GEOCHAT_VQA_PROVIDER=development`
- Does not modify the service API or request/response contracts
- Does not commit tokens, weights, or validation imagery
