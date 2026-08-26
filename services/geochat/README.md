# GeoChat Inference Service (Phase 14)

Standalone HTTP service hosting **MBZUAI/geochat-7B** for SatQuery single-image VQA and scene captioning.

## Architecture

```
SatQuery backend  --HTTP-->  GeoChat Service  --GPU-->  MBZUAI/geochat-7B
```

The backend remains model-agnostic. Set:

```bash
GEOCHAT_VQA_PROVIDER=geochat_service
GEOCHAT_SERVICE_URL=http://<gpu-host>:8080
```

Development mode (`GEOCHAT_VQA_PROVIDER=development`) is unchanged.

## GPU host setup (Tesla T4)

1. Clone GeoChat upstream:

```bash
git clone https://github.com/mbzuai-oryx/GeoChat.git /opt/geochat
```

2. Install service + GPU dependencies:

```bash
cd services/geochat
pip install -e ".[gpu]"
```

3. Export environment:

```bash
export GEOCHAT_SRC=/opt/geochat
export GEOCHAT_MODEL_ID=MBZUAI/geochat-7B
export HF_TOKEN=...   # never commit
export GEOCHAT_EAGER_LOAD=true
```

4. Run:

```bash
uvicorn geochat_service.main:app --host 0.0.0.0 --port 8080
```

Loading uses the verified Phase 9B strategy:

- `load_in_8bit=True`
- `device_map="auto"`
- `low_cpu_mem_usage=True`
- deferred CLIP 336→504 interpolation after checkpoint load

## API

### `GET /health`

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_name": "MBZUAI/geochat-7B",
  "gpu": "Tesla T4",
  "provider": "geochat_service",
  "service_version": "0.1.0",
  "load_strategy": "geochat_upstream_8bit_device_map_auto_deferred_clip504"
}
```

### `POST /v1/vqa`

Request body matches `backend/app/schemas/geochat_service.py`:

- `image.content_base64` — raster bytes (no filesystem paths)
- `image_metadata` — image ID, modality, CRS, bounds (for logging only)
- `question` — user question

### `POST /v1/caption`

Same image transfer contract with `user_request` and `mode: "scene_description"`.

## Failure behavior

If the model cannot load or CUDA is unavailable, the service returns **HTTP 503** with an explicit error. The backend does **not** fall back to development mock or generic LLMs when `geochat_service` is configured.

## Local validation (no GPU)

Service unit tests use `GEOCHAT_SERVICE_FAKE_ENGINE=true` for preprocessing and HTTP contract checks only.

Real GPU validation:

```bash
GEOCHAT_REAL_SERVICE_TEST=true GEOCHAT_SERVICE_URL=http://gpu-host:8080 pytest backend/tests/test_phase14_geochat_service.py -k real_service
```

Save artifacts to `services/geochat/validation_artifacts/` (gitignored).
