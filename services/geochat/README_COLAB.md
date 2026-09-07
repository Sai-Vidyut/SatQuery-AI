# GeoChat Service — Google Colab T4 Validation (Phase 16)

Temporary Colab launcher for **real** `MBZUAI/geochat-7B` inference using the **existing** `services/geochat` FastAPI service.

- Starts only the GeoChat HTTP service (`GET /health`, `POST /v1/vqa`, `POST /v1/caption`)
- Does **not** start the SatQuery backend
- Does **not** use the development/mock provider
- Preserves the existing byte/base64 image API (no filesystem paths)

**Colab port note:** Google Colab reserves **port 8080** for its Node process (PID 7). Do **not** bind GeoChat to 8080. Colab validation uses **port 8000** only.

---

## Recommended: one-click notebook

Upload **`services/geochat/colab_phase16_validation.ipynb`** to Google Colab, set runtime to **T4 GPU**, add Colab Secret **`HF_TOKEN`**, then **Runtime → Run all**.

The notebook orchestrates clone, service start on **:8000**, health polling, VQA, caption, backend adapter validation, and optional ngrok on **8000**. Artifacts: `/content/phase16_geochat_validation/`.

---

## Manual shell launcher (alternative)

### 1. Clone the repository

```python
!git clone https://github.com/Sai-Vidyut/SatQuery-AI.git /content/SatQuery-AI
%cd /content/SatQuery-AI
```

### 2. Configure GPU runtime

In Colab: **Runtime → Change runtime type → T4 GPU**

### 3. Configure HF_TOKEN (if required)

Add Colab Secret **`HF_TOKEN`** (sidebar key icon). The launcher reads `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` from the environment only — never hardcoded.

### 4. Start the GeoChat service

**Must run from the repository root.** Default listen port is **8000** (not 8080).

```python
%cd /content/SatQuery-AI
!bash services/geochat/scripts/colab_start.sh
```

Override port (optional):

```python
import os
os.environ["GEOCHAT_PORT"] = "8000"  # Colab default; do not use 8080
!bash services/geochat/scripts/colab_start.sh
```

This cell stays alive while uvicorn runs in the foreground. First start downloads `MBZUAI/geochat-7B` weights (several minutes).

Loading uses the verified Phase 9B strategy implemented in `geochat_service/inference.py`:

- `load_in_8bit=True`
- `device_map="auto"`
- `low_cpu_mem_usage=True`
- deferred CLIP 336→504 interpolation after checkpoint load

### 5. Verify `/health` (second Colab cell)

While the service cell is still running:

```python
!curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Expected:

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

### 6. Expose port 8000 for Phase 16 validation from your machine

`127.0.0.1:8000` is only reachable inside Colab. For local SatQuery backend validation, expose port **8000** temporarily. **Do not tunnel 8080** (Colab Node).

#### Option A — ngrok (recommended)

```python
!pip install -q pyngrok
from pyngrok import ngrok
public_url = ngrok.connect(8000)
print("Public GeoChat service URL:", public_url)
```

#### Option B — localtunnel

```python
!npm install -g localtunnel
!lt --port 8000
```

### Connect your local SatQuery backend

Use `GEOCHAT_SERVICE_URL` with your tunnel URL (any port/host — not hardcoded in production):

```bash
export GEOCHAT_VQA_PROVIDER=geochat_service
export GEOCHAT_SERVICE_URL=https://<your-tunnel-host>   # ngrok / localtunnel URL
export GEOCHAT_MODEL_ID=MBZUAI/geochat-7B

cd backend
uv run python ../services/geochat/scripts/run_phase16_validation.py
```

Or run the gated integration test:

```bash
GEOCHAT_REAL_SERVICE_TEST=true GEOCHAT_SERVICE_URL=https://<your-tunnel-host> \
  uv run pytest tests/test_phase14_geochat_service.py -k real_service -v
```

---

## What gets installed

| Component | Installed by launcher? |
|-----------|------------------------|
| `services/geochat` (FastAPI app) | ✅ `pip install -e services/geochat` |
| transformers 4.36.2, bitsandbytes, accelerate, etc. | ✅ Phase 9B pinned stack |
| Colab `torch` / CUDA | ❌ not reinstalled |
| GeoChat upstream (`mbzuai-oryx/GeoChat`) | ✅ cloned to `/content/geochat` |
| SatQuery `backend/` | ❌ not started |
| Model weights | ⏳ on first uvicorn start only |

## Environment variables (Colab)

| Variable | Default (Colab) | Description |
|----------|-----------------|-------------|
| `GEOCHAT_PORT` | `8000` | Colab-friendly port alias (preferred) |
| `GEOCHAT_SERVICE_PORT` | `8000` | Passed to `geochat_service` config |
| `GEOCHAT_SRC` | `/content/geochat` | GeoChat upstream clone path |
| `GEOCHAT_MODEL_ID` | `MBZUAI/geochat-7B` | Hugging Face model id |
| `GEOCHAT_EAGER_LOAD` | `true` | Load model when service starts |
| `GEOCHAT_COLAB_MEMORY_PROFILE` | `colab` | Enables cpu=2GiB + disk=40GiB offload caps |
| `GEOCHAT_OFFLOAD_DIR` | `/content/geochat_offload` | Disk spillover during 8-bit load |
| `GEOCHAT_SERVICE_HOST` | `0.0.0.0` | Bind address |
| `HF_TOKEN` | — | Hugging Face auth (Colab Secret) |

Production GPU hosts may still use port **8080** via `GEOCHAT_SERVICE_URL` — that default is unchanged in `geochat_service/config.py`.

`GEOCHAT_SERVICE_FAKE_ENGINE` is explicitly unset.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Address already in use` on 8080 | Use port **8000** — Colab Node owns 8080 |
| `Run this script from the SatQuery-AI repository root` | `%cd /content/SatQuery-AI` then re-run |
| `CUDA GPU is unavailable` | Runtime → T4 GPU, restart runtime |
| `bitsandbytes` CUDA error | Restart runtime; re-run launcher |
| `model_loaded: false` in `/health` | Wait for HF download; check `HF_TOKEN` |
| `exit_code: -9` during CELL 6 | **OOM** — use **High-RAM** runtime, or pull latest `sai/core-ai` (disk offload). Log must show `cpu: 2GiB`, `disk: 40GiB` |
| Tunnel connects but health fails | Ensure uvicorn is listening on **8000** |

### OOM alternatives (exit -9)

| Option | Notes |
|--------|--------|
| **Colab High-RAM** | Best fix — Runtime → Change runtime type → High-RAM |
| **Disk offload (built-in)** | `GEOCHAT_COLAB_MEMORY_PROFILE=colab` spills weights to `/content/geochat_offload` |
| **Kaggle Notebooks** | ~30 GB RAM + free GPU; same `services/geochat` launcher |
| **Local GPU** | Run `services/geochat` on a machine with ≥16 GB system RAM + T4-class VRAM |
| **Development mock** | On Mac: `GEOCHAT_VQA_PROVIDER=development` (no real GeoChat inference) |

## What this does NOT do

- Does not kill or interfere with Colab's Node process on port 8080
- Does not modify SatQuery backend behavior or production API contracts
- Does not modify the Phase 9B smoke-test notebook
- Does not add fake/mock inference
- Does not commit tokens, weights, or imagery

See also: `docs/SIH_PHASE16_VALIDATION.md`
