# GeoChat Developer Tooling

Local-only helpers for validating the **real** GeoChat GPU service. This does not run inside the SatQuery application at request time.

## Modes

| Mode | `GEOCHAT_VQA_PROVIDER` | Requires |
|------|------------------------|----------|
| Local (default) | `development` | Nothing — deterministic mock |
| Real GPU | `geochat_service` | Live `GEOCHAT_SERVICE_URL` |

Copy `backend/.env.geochat-real.example` into `backend/.env` and paste your tunnel URL. **Never commit** `backend/.env`.

## Developer manager

From repo root:

```bash
python services/geochat/scripts/geochat_dev.py status
python services/geochat/scripts/geochat_dev.py health
python services/geochat/scripts/geochat_dev.py wait-ready --timeout 600
python services/geochat/scripts/geochat_dev.py smoke-test --composite
python services/geochat/scripts/geochat_dev.py acceptance
python services/geochat/scripts/geochat_dev.py start   # prints manual Colab steps
```

Exit codes:

- `0` — success / ready
- `1` — misconfigured or not ready
- `2` — **BLOCKED** (service unavailable — not a pass)

## What is automatable

- Health polling (`wait-ready`)
- Direct `/v1/vqa` smoke tests (single image + evidence composite)
- Full acceptance runner (`acceptance`)
- Opt-in pytest (`GEOCHAT_REAL_SERVICE_TEST=true`)
- SatQuery adapter composite call verification

## What still requires manual interaction

| Step | Why manual |
|------|------------|
| Colab runtime → T4 GPU | Google Colab UI |
| Colab Secrets (`HF_TOKEN`, `NGROK_AUTHTOKEN`) | Credentials |
| Upload/run notebook or `colab_start.sh` | Platform session |
| ngrok tunnel creation | Ephemeral URL + auth token |
| Keep Colab/Kaggle session alive | Session lifetime |
| Paste tunnel URL into `backend/.env` | Local secret handling |

Kaggle is documented as an OOM alternative but has **no checked-in Phase 16 kernel**. Do not expect Cursor/browser automation to restart Kaggle reliably.

## Real service architecture (summary)

```
Colab T4 / GPU host
  └─ uvicorn geochat_service.main:app  (port 8000 Colab, 8080 bare host)
       ├─ GET  /health        → model_loaded, status, gpu
       ├─ POST /v1/vqa        → base64 image bytes
       └─ POST /v1/caption
            ↑
     ngrok / localtunnel (HTTPS)
            ↑
Mac backend (.env)
  GEOCHAT_VQA_PROVIDER=geochat_service
  GEOCHAT_SERVICE_URL=https://…
            ↑
SatQuery GeoChatServiceVLM → region interpretation / VQA / caption
```

## Real region interpretation acceptance (manual UI)

When `geochat_dev.py acceptance` returns **PASS**:

1. Set real provider in `backend/.env`
2. Restart backend
3. Open http://localhost:3002
4. Upload vegetation_loss before/after pair
5. Run bi-temporal analysis → select region
6. Verify Before/After preview
7. Click **Interpret this region**
8. Confirm badge **REAL GeoChat-7B**, provider `geochat_service`, no `[development mock` in answer
9. Confirm deterministic detection block remains visible

## Opt-in tests

```bash
# Service-side acceptance helpers
cd services/geochat && pytest tests/test_geochat_dev.py -q

# Backend real provider (requires live service)
cd backend
GEOCHAT_REAL_SERVICE_TEST=true GEOCHAT_SERVICE_URL=https://YOUR-TUNNEL \
  .venv/bin/pytest tests/test_geochat_real_provider.py -q
```

If the GPU service is unavailable, tests report **BLOCKED** (skip) — never PASS.
