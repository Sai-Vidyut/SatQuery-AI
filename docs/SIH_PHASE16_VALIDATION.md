# SIH Phase 16 — Real-World Provider Validation Report

**Date:** 2026-08-26  
**Phase type:** Validation only (no new product capabilities)  
**Auditor environment:** macOS aarch64, no local CUDA, no `GEOCHAT_SERVICE_URL` configured

---

## 1. Executive summary

Phase 16 attempted to validate which **already-implemented** workflows work with **real data and real providers**. Automated contract and negative-path tests **passed**. **Real GPU GeoChat HTTP service validations did not run** in this environment because no GPU host was available and `GEOCHAT_SERVICE_URL` was not set.

| Capability | IMPLEMENTED | AUTOMATED TESTED | REAL DATA VALIDATED | REAL MODEL VALIDATED | PRODUCTION SERVICE VALIDATED |
|------------|-------------|------------------|---------------------|----------------------|------------------------------|
| Single-image VQA | ✅ | ✅ | ⚠️ Colab only | ⚠️ Colab only | ❌ |
| Scene caption | ✅ | ✅ | ❌ | ❌ | ❌ |
| Bi-temporal change | ✅ | ✅ | ❌ | N/A | ❌ |
| Optical + SAR | ✅ | ✅ | ❌ | N/A | ❌ |
| GeoChat HTTP service | ✅ | ✅ (fake engine) | ❌ | ❌ | ❌ |
| Earth Engine catalog | ✅ | ✅ (dev/EE unit tests) | ❌ (not exercised here) | N/A | ❌ |

**Bottom line:** Architecture and automated tests are solid. **Production GeoChat service validation remains the P0 blocker** before claiming a real-model SIH demo.

---

## 2. Validation environment

| Item | Value |
|------|-------|
| Host OS | darwin (macOS aarch64) |
| Local CUDA / `nvidia-smi` | Not available |
| `torch` (local) | Not installed |
| `GEOCHAT_SERVICE_URL` | **Not set** |
| `GEOCHAT_REAL_SERVICE_TEST` | **Not set** |
| `GEOCHAT_VQA_PROVIDER` (validation runs) | `development` (default for automated suites) |

**Prior real-model evidence (not re-run in Phase 16):**

- Phase 9B Colab T4 smoke test: `MBZUAI/geochat-7B` loaded in 8-bit, genuine inference on `experiments/phase9b_geochat/assets/sentinel2_smoketest.png` (real Sentinel-2 L2A, Vienna AOI).
- This validates **real model inference in Colab**, not the standalone `services/geochat/` HTTP deployment.

---

## 3. Test suite results (verified 2026-08-26)

| Suite | Command | Result |
|-------|---------|--------|
| Backend pytest | `cd backend && uv run pytest -q` | **241 passed**, 3 skipped |
| GeoChat service pytest | `cd services/geochat && uv run pytest -q` | **6 passed** |
| Frontend Vitest | `cd frontend && npm run test -- --run` | **9 passed** |
| Playwright E2E | `cd frontend && npx playwright test` | **8 passed** |
| Frontend build | `cd frontend && npm run build` | **Success** |
| Phase 14 integration | `cd backend && uv run pytest tests/test_phase14_geochat_service.py -q` | **16 passed**, 1 skipped |

**Skipped tests (backend):**

- 2× malformed-raster upload rejects at ingest
- 1× `test_real_geochat_service_integration` — requires `GEOCHAT_REAL_SERVICE_TEST=true` + live GPU service

**No GPU inference was executed during this phase.**

---

## 4. P0 — Real GeoChat service validations

### Validation 1 — GeoChat health (`GET /health`)

| Field | Result |
|-------|--------|
| Status | **NOT VALIDATED** |
| Blocker | `GEOCHAT_SERVICE_URL` not set; no GPU service reachable |
| Expected artifact | `services/geochat/validation_artifacts/real_health.json` |
| Actual | Not created |

**Command when GPU host is available:**

```bash
export GEOCHAT_SERVICE_URL=http://<gpu-host>:8080
curl -s "$GEOCHAT_SERVICE_URL/health" | jq .
# or:
cd backend && uv run python ../services/geochat/scripts/run_phase16_validation.py
```

---

### Validation 2 — Direct real GeoChat VQA (`POST /v1/vqa`)

| Field | Result |
|-------|--------|
| Status | **NOT VALIDATED** |
| Image | `experiments/phase9b_geochat/assets/sentinel2_smoketest.png` (real Sentinel-2) |
| Question | "Describe the main land-cover types visible in this satellite image." |
| Expected artifact | `services/geochat/validation_artifacts/real_vqa.json` |
| Actual | Not created |

**Command:**

```bash
export GEOCHAT_SERVICE_URL=http://<gpu-host>:8080
export GEOCHAT_MODEL_ID=MBZUAI/geochat-7B
cd backend && uv run python ../services/geochat/scripts/run_real_validation.py
```

---

### Validation 3 — Backend → GeoChat service (full path)

| Field | Result |
|-------|--------|
| Status | **NOT VALIDATED** |
| Blocker | No live GeoChat service; backend E2E not run with `geochat_service` |
| Expected artifact | `services/geochat/validation_artifacts/real_backend_vqa_result.json` |

**Required setup:**

```bash
# Terminal 1 — GPU host
cd services/geochat
export GEOCHAT_SRC=/opt/geochat GEOCHAT_EAGER_LOAD=true
uvicorn geochat_service.main:app --host 0.0.0.0 --port 8080

# Terminal 2 — backend
cd backend
export GEOCHAT_VQA_PROVIDER=geochat_service
export GEOCHAT_SERVICE_URL=http://<gpu-host>:8080
uv run uvicorn app.main:app --port 8000

# Terminal 3 — validation
export GEOCHAT_SERVICE_URL=http://<gpu-host>:8080
export SATQUERY_BACKEND_URL=http://127.0.0.1:8000
cd backend && uv run python ../services/geochat/scripts/run_phase16_validation.py
```

**Automated contract proxy (fake engine, not real model):** `test_02_valid_vqa_request`, `test_12_single_image_vqa_regression_api` — **PASS** (development provider in API regression test).

---

### Validation 4 — Real GeoChat caption

| Field | Result |
|-------|--------|
| Status | **NOT VALIDATED** |
| Expected artifact | `services/geochat/validation_artifacts/real_caption.json` |
| Actual | Not created |

**Automated contract proxy:** `test_13_caption_regression`, GeoChat service `test_caption_endpoint` — **PASS** (fake engine / development provider).

---

### Validation 5 — Uploaded raster path (real GeoTIFF, bytes-only to service)

| Field | Result |
|-------|--------|
| Status | **PARTIAL** |
| Real GeoTIFF prepared | ✅ `validation_artifacts/sentinel2_smoketest_georef.tif` |
| Source | Real Sentinel-2 smoke PNG + WGS84 bounds from `sentinel2_smoketest.metadata.json` |
| Manifest | `validation_artifacts/georef_geotiff_manifest.json` |
| Upload → real GeoChat | **NOT VALIDATED** (no GPU service) |
| Bytes-not-paths contract | **AUTOMATED TESTED** — `test_06_adapter_sends_bytes_not_paths` **PASS** |

**Honesty:** GeoTIFF is derived from the verified real Sentinel-2 PNG (not a synthetic zero raster). End-to-end upload → real GeoChat was **not** exercised.

---

### Validation 6 — Bi-temporal upload path

| Field | Result |
|-------|--------|
| Status | **AUTOMATED TESTED only** |
| Implementation exercised | `DeterministicChangeDetector` via upload bridge + `change_understanding` template |
| Real satellite pair | **Not available** in this validation run |
| GeoChat change detection | **Not claimed** — change understanding is template from CVA evidence, not RS-VLM |

| Classification | Value |
|----------------|-------|
| IMPLEMENTED | ✅ |
| AUTOMATED TESTED | ✅ (`test_phase12_*`, `test_14_bi_temporal_regression`, Playwright `bi-temporal-change.spec.ts`) |
| REAL DATA VALIDATED | ❌ |
| REAL MODEL VALIDATED | N/A |
| PRODUCTION SERVICE VALIDATED | ❌ |

**Limitation:** Test and E2E fixtures use minimal synthetic GeoTIFFs (`tests/fixtures/rasters.py`). No validated real bi-temporal Sentinel pair was uploaded in Phase 16.

---

### Validation 7 — Real optical + SAR path

| Field | Result |
|-------|--------|
| Status | **AUTOMATED TESTED only** |
| Specialists exercised | `development_uploaded_optical_analyzer`, `development_uploaded_sar_analyzer` |
| Fusion policy | `uploaded_cross_modal_fusion_v1.0.0` |
| Co-registration | `overlap_only_not_verified` (default); no verified benchmark pair used |
| Real optical+SAR pair | **Not available** in this validation run |

| Classification | Value |
|----------------|-------|
| IMPLEMENTED | ✅ |
| AUTOMATED TESTED | ✅ (`test_phase13_*`, `test_15_cross_modal_regression`, Playwright `cross-modal.spec.ts`) |
| REAL DATA VALIDATED | ❌ |
| REAL MODEL VALIDATED | N/A |
| PRODUCTION SERVICE VALIDATED | ❌ |

**Do not claim:** true co-registration, real SAR backscatter analysis, or production fusion.

---

### Validation 8 — Negative tests (no GPU required)

| Test | Result | Evidence |
|------|--------|----------|
| Service unavailable | **PASS** | `test_08_service_unavailable` |
| Service timeout | **PASS** | `test_07_timeout_handling` |
| Malformed VQA request | **PASS** | `test_03_malformed_request`, service `test_malformed_request` |
| Missing image | **PASS** | `test_04_missing_image`, service `test_missing_image` |
| Missing question | **PASS** | `test_05_missing_question`, service `test_missing_question` |
| Invalid upload | **PASS** | `test_upload_api.py`, phase 10/12/13 upload rejection tests |
| Unsupported production JPEG | **PASS** | `test_sih_04_unsupported_jpeg_without_benchmark` |
| Development provider still works | **PASS** | `test_11_development_provider_regression`, conftest `force_development_providers` |

---

### Validation 9 — No silent fallback

| Check | Result | Evidence |
|-------|--------|----------|
| `geochat_service` timeout → explicit error | **PASS** | `SatQueryError` code `geochat_service_timeout` |
| `geochat_service` unavailable → explicit error | **PASS** | `SatQueryError` code `geochat_service_error` |
| No fallback to development mock | **PASS** | Adapter raises; `query_controller` propagates `SatQueryError` |
| No fabricated answer on failure | **PASS** | No catch-and-template in `geochat_service.py` adapter |

**Not re-run against live API** with `GEOCHAT_VQA_PROVIDER=geochat_service` and dead service URL in Phase 16; adapter-level proof is from automated tests.

---

### Validation 10 — Provenance

| Field | Policy | Phase 16 status |
|-------|--------|-----------------|
| `model_name` | Required on real results | Contract tests assert `MBZUAI/geochat-7B` |
| `provider` | Required | `geochat_service` or `development` (labeled) |
| `confidence_available` | Must be `false` when uncalibrated | **PASS** (`test_10_no_fake_confidence`) |
| Service URL in provenance | Host only, no secrets | **PASS** (`test_09_provenance`) |
| No HF tokens / local paths in artifacts | Required | Validation scripts redact URL host only |

Real GeoChat result artifacts (`real_vqa.json`, etc.) were **not produced** (no GPU run).

---

## 5. Capability classification (required format)

### 1. Single-image VQA

| | |
|-|-|
| **IMPLEMENTED** | ✅ Upload path, planner `single_image_vqa`, `geochat_vqa` tool, GUI, trace |
| **AUTOMATED TESTED** | ✅ 241 backend tests include phase 10; Playwright `upload-vqa.spec.ts` |
| **REAL DATA VALIDATED** | ⚠️ **Colab only** — real Sentinel-2 PNG (Phase 9B); not via SatQuery upload + HTTP service |
| **REAL MODEL VALIDATED** | ⚠️ **Colab only** — `MBZUAI/geochat-7B` on T4; not via `services/geochat/` deployment |
| **PRODUCTION SERVICE VALIDATED** | ❌ |
| **NOT VALIDATED** | Backend upload → `geochat_service` → real inference |

### 2. Scene caption

| | |
|-|-|
| **IMPLEMENTED** | ✅ `single_image_caption`, `geochat_caption`, GUI, trace |
| **AUTOMATED TESTED** | ✅ Phase 11 tests; Playwright `scene-caption.spec.ts` |
| **REAL DATA VALIDATED** | ❌ |
| **REAL MODEL VALIDATED** | ❌ |
| **PRODUCTION SERVICE VALIDATED** | ❌ |
| **NOT VALIDATED** | `POST /v1/caption` and backend caption path with real GPU service |

### 3. Bi-temporal change

| | |
|-|-|
| **IMPLEMENTED** | ✅ Pair upload, `validate_bi_temporal`, CVA bridge, `change_understanding` |
| **AUTOMATED TESTED** | ✅ Phase 12; Playwright `bi-temporal-change.spec.ts` |
| **REAL DATA VALIDATED** | ❌ (synthetic test rasters only in automated runs) |
| **REAL MODEL VALIDATED** | N/A — CVA is `DeterministicChangeDetector`, not RS-VLM |
| **PRODUCTION SERVICE VALIDATED** | ❌ |
| **NOT VALIDATED** | Real uploaded-raster CVA on true change pair |

**Implementation truth:** `CHANGE_DETECTOR=development` on upload path. Not Earth Engine CVA.

### 4. Optical + SAR

| | |
|-|-|
| **IMPLEMENTED** | ✅ Modality validation, fusion stage, GUI, trace |
| **AUTOMATED TESTED** | ✅ Phase 13; Playwright `cross-modal.spec.ts` |
| **REAL DATA VALIDATED** | ❌ |
| **REAL MODEL VALIDATED** | N/A — development optical/SAR specialists |
| **PRODUCTION SERVICE VALIDATED** | ❌ |
| **NOT VALIDATED** | Real optical+SAR pair; verified co-registration |

### 5. GeoChat HTTP service

| | |
|-|-|
| **IMPLEMENTED** | ✅ `services/geochat/` FastAPI, byte transfer, 8-bit load path |
| **AUTOMATED TESTED** | ✅ 6 service tests (fake engine); 16 phase 14 tests |
| **REAL DATA VALIDATED** | ❌ |
| **REAL MODEL VALIDATED** | ❌ (Colab ≠ HTTP service) |
| **PRODUCTION SERVICE VALIDATED** | ❌ |
| **NOT VALIDATED** | T4 deployment, `/health` with `model_loaded=true` on GPU, real VQA/caption |

### 6. Earth Engine catalog workflow

| | |
|-|-|
| **IMPLEMENTED** | ✅ Phases 2–7 EE providers, CVA, DW, SAR, fusion |
| **AUTOMATED TESTED** | ✅ EE unit tests; Playwright `flagship.spec.ts` (development imagery in CI) |
| **REAL DATA VALIDATED** | ❌ Not exercised in Phase 16 |
| **REAL MODEL VALIDATED** | N/A |
| **PRODUCTION SERVICE VALIDATED** | ❌ |
| **NOT VALIDATED** | Live EE credentials end-to-end in this phase |

---

## 6. Artifact index

All under `services/geochat/validation_artifacts/` (gitignored):

| Artifact | Created | Description |
|----------|---------|-------------|
| `phase16_runner_report.json` | ✅ | Runner blocker: no `GEOCHAT_SERVICE_URL` |
| `phase16_summary.json` | ✅ | Test counts + validation status summary |
| `georef_geotiff_manifest.json` | ✅ | Real Sentinel-2 → GeoTIFF provenance |
| `sentinel2_smoketest_georef.tif` | ✅ | Real-data GeoTIFF for future upload validation |
| `real_health.json` | ❌ | Requires GPU service |
| `real_vqa.json` | ❌ | Requires GPU service |
| `real_caption.json` | ❌ | Requires GPU service |
| `real_backend_vqa_result.json` | ❌ | Requires GPU service + running backend |

---

## 7. Failures and blockers

| Blocker | Impact |
|---------|--------|
| No `GEOCHAT_SERVICE_URL` / no GPU host | Validations 1–4, 3, 5 (E2E) blocked |
| No live backend + GPU stack | Full upload → query → real GeoChat path not run |
| No real bi-temporal satellite pair on disk | Validation 6 real-data portion blocked |
| No real optical+SAR benchmark pair | Validation 7 real-data portion blocked |

**No test regressions.** No failures in automated suites.

---

## 8. Limitations (explicit)

- Colab Phase 9B success **does not** prove `services/geochat/` production deployment.
- Fake-engine HTTP tests **do not** prove `MBZUAI/geochat-7B` loads on the standalone service.
- Playwright E2E uses **development** GeoChat provider (default backend test config).
- Bi-temporal and cross-modal paths use **development** specialists — honest labels preserved in traces.
- **Grounding, fine-tuning, change-VQA with RS-VLM** — not implemented; not validated.

---

## 9. What remains unvalidated

1. Deploy `services/geochat` on T4 with `GEOCHAT_EAGER_LOAD=true`
2. `GET /health` with `model_loaded=true` and GPU reported
3. `POST /v1/vqa` and `POST /v1/caption` with genuine model output (not fake engine)
4. SatQuery backend with `GEOCHAT_VQA_PROVIDER=geochat_service` on uploaded real GeoTIFF
5. `GEOCHAT_REAL_SERVICE_TEST=true` integration test
6. Real bi-temporal pair → CVA on uploaded rasters (production detector)
7. Real optical+SAR pair with honest co-registration status

---

## 10. Recommended next steps (validation only)

```bash
# On GPU host
cd services/geochat && pip install -e ".[gpu]"
export GEOCHAT_SRC=/opt/geochat GEOCHAT_MODEL_ID=MBZUAI/geochat-7B GEOCHAT_EAGER_LOAD=true
uvicorn geochat_service.main:app --host 0.0.0.0 --port 8080

# From dev machine
export GEOCHAT_SERVICE_URL=http://<gpu-host>:8080
export GEOCHAT_REAL_SERVICE_TEST=true
cd backend && uv run python ../services/geochat/scripts/run_phase16_validation.py
cd backend && GEOCHAT_REAL_SERVICE_TEST=true GEOCHAT_SERVICE_URL=$GEOCHAT_SERVICE_URL uv run pytest tests/test_phase14_geochat_service.py -k real_service -v
```

Follow acceptance procedures in `docs/SIH_ACCEPTANCE_SINGLE_IMAGE_VQA.md` and `docs/SIH_ACCEPTANCE_SINGLE_IMAGE_SCENE_DESCRIPTION.md`.

---

## 11. DO NOT IMPLEMENT YET

Per Phase 15 audit — unchanged:

- Grounding
- RS-VLM change-VQA
- LoRA / fine-tuning
- Reference-mask evaluation
- PostgreSQL, auth, reports
- Claiming production-ready without GPU service evidence

---

## MANDATORY VALIDATIONS REMAINING

- Real GeoChat HTTP service health, VQA, and caption on GPU
- Backend full path with `geochat_service` on uploaded real GeoTIFF
- Real bi-temporal uploaded-raster validation (if required for SIH demo)
- Real optical+SAR validation (if required for SIH demo)

## VALIDATION ONLY (next run)

- Deploy GPU service; run `run_phase16_validation.py` and `GEOCHAT_REAL_SERVICE_TEST=true`
- Save `real_vqa.json`, `real_caption.json`, `real_health.json`, `real_backend_vqa_result.json`

## PASSED IN PHASE 16 (no GPU)

- All automated test suites (241 + 6 + 9 + 8 backend/phase14 subsets)
- Negative paths and no-fallback contract tests
- Real Sentinel-2 GeoTIFF preparation for future upload validation
- Frontend production build

---

*Phase 16 complete. No Phase 17 work started.*
