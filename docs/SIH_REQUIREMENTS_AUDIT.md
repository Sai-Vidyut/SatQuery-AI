# SIH Mandatory Requirements Audit (Phase 15)

**Date:** 2026-08-26  
**Scope:** Phases 8–14 complete. Audit only — no production code changes.  
**Auditor basis:** Repository evidence only (no external PDF of the official SIH problem statement is checked into this repo).

---

## 1. Executive summary

SatQuery AI has implemented the **upload-centric SIH workflow architecture** for Phases 8–14: unified input validation, four distinct analysis modes (single-image VQA, scene caption, bi-temporal change, cross-modal optical+SAR), agentic planner routing, observable traces, GUI composer modes, and a standalone GeoChat HTTP service adapter.

**What is solid (architecture + automated tests):**

| Area | Verdict |
|------|---------|
| Input foundation (Phase 8) | **PASS** (automated) |
| Single-image VQA routing + GUI + trace (Phase 10) | **PASS** (automated; mock provider) |
| Single-image scene caption routing + GUI + trace (Phase 11) | **PASS** (automated; mock provider) |
| Bi-temporal upload change workflow (Phase 12) | **PARTIAL** (automated; development CVA only) |
| Cross-modal optical+SAR workflow (Phase 13) | **PARTIAL** (automated; development specialists only) |
| GeoChat service architecture (Phase 14) | **PASS** (automated contract tests; GPU service not end-to-end validated) |
| Earth Engine catalog workflow (Phases 1–7) | **PASS** (automated; separate from upload SIH demos) |

**What remains for a credible SIH production demonstration:**

1. **End-to-end real GeoChat inference** through the deployed HTTP service on uploaded GeoTIFF (not Colab-only, not development mock).
2. **Honest production specialists** for uploaded bi-temporal CVA, cross-modal optical/SAR analysis, and fusion (currently development mocks on upload path).
3. **Clarification of grounding** — early research notes (`Phase 9A`) list VQA **+ grounding** as mandatory single-image tasks; Phases 10–11 implemented **caption** as the second single-image capability instead. Grounding is **not implemented**.

**What is explicitly out of scope / not mandatory per repo docs:**

Grounding, change-VQA with RS-VLM, fine-tuning, reference-mask benchmark evaluation, PostgreSQL/PostGIS, auth, reports.

---

## 2. Source of “official” requirements

The repository does **not** contain a verbatim SIH problem-statement PDF. Mandatory requirements below are reconstructed from:

| Source | What it establishes |
|--------|---------------------|
| Phase 8–14 implementation prompts (conversation + `AGENTS.md`) | Upload workflows, planner, trace, evidence honesty |
| `docs/SIH_ACCEPTANCE_*.md` (4 files) | Acceptance procedures for VQA, caption, bi-temporal, cross-modal |
| `README.md` | SIH 2026 positioning; explicit “not implemented” list |
| `experiments/phase9a_geochat_smoketest/` notes | Research decision: GeoChat-7B; “VQA + grounding” as mandatory single-image tasks (research phase) |
| `AGENTS.md` Phase 15+ | Grounding, change-VQA marked not started |

Where the sources disagree (grounding vs caption), the audit marks **UNKNOWN** or **PARTIAL** and explains the conflict.

---

## 3. Requirement-by-requirement matrix

Legend: **PASS** | **PARTIAL** | **FAIL** | **NOT VALIDATED** | **OPTIONAL** | **UNKNOWN**

### A. Platform & input foundation

| Requirement | Mandatory? | Current implementation | Status | Evidence | Missing work | Next phase |
|-------------|------------|------------------------|--------|----------|--------------|------------|
| Unified imagery input (`ImageInput`, upload storage) | Yes | Phase 8 `schemas/input.py`, `UploadedImageryProvider`, `UPLOAD_DIR` | **PASS** | `test_upload_api.py`, `test_upload_storage.py`, `test_input_schemas.py` | — | — |
| GeoTIFF/TIFF upload validation (readable, georeferenced) | Yes | `validate_single_image()`, upload API | **PASS** | Phase 8/10/12/13 tests | — | — |
| Optical / multispectral / SAR modality metadata | Yes | `ImageModality`, upload form `modality` | **PASS** | `test_phase13` modality checks | — | — |
| Bi-temporal pair compatibility (overlap, dates) | Yes | `validate_bi_temporal()` | **PASS** | `test_phase12_bi_temporal_change.py` | — | — |
| Optical+SAR pair compatibility (modality, overlap) | Yes | `validate_optical_sar_pair()` | **PASS** | `test_phase13_cross_modal_optical_sar.py` | — | — |
| Honest co-registration status (no false claims) | Yes | `resolve_co_registration_status()`, benchmark pair tokens | **PASS** | Phase 13 tests 6–7; `overlap_only_not_verified` default | Real co-registered benchmark dataset validation | Validation |
| PNG/JPEG only via `benchmark_dataset=true` | Yes | `validate_extension_and_format()`, upload API | **PASS** | Phase 10/13 JPEG policy tests | — | — |
| Catalog Earth Engine path (AOI + dates) | Unknown (SIH upload track) | Phases 2–7 EE providers, frontend catalog mode | **PASS** (catalog) | `flagship.spec.ts`, EE tests | Not required for upload SIH demo | — |

### B. Agentic orchestration (cross-cutting)

| Requirement | Mandatory? | Current implementation | Status | Evidence | Missing work | Next phase |
|-------------|------------|------------------------|--------|----------|--------------|------------|
| Natural-language → constrained planner (`QueryAnalysisPlan`) | Yes | Phase 6 planner + upload-mode branches in `deterministic.py` | **PASS** | Planner tests in phase 10–13 | LLM planner optional | — |
| Correct intent per upload mode | Yes | `single_image_vqa`, `single_image_caption`, `bi_temporal_change_vqa`, `cross_modal_optical_sar` | **PASS** | Phase 10–13 intent tests | — | — |
| Specialist tool execution (not answer-only LLM) | Yes | Dedicated tools per workflow | **PASS** | Trace steps in controller tests | — | — |
| Observable execution trace | Yes | `TraceStep` chain in `query_controller.py` | **PASS** | All phase E2E specs show trace | — | — |
| Evidence-grounded answers (no invented metrics/regions) | Yes | Evidence engine, `confidence_available=false` when uncalibrated | **PASS** | Phase 10–13 “no fabricated confidence” tests | — | — |
| GUI workstation for each upload workflow | Yes | Composer modes: Upload, Temporal pair, Cross-modal | **PASS** | Playwright E2E (8 tests) | — | — |

### C. Single-image RS-VLM (GeoChat)

| Requirement | Mandatory? | Current implementation | Status | Evidence | Missing work | Next phase |
|-------------|------------|------------------------|--------|----------|--------------|------------|
| Single-image VQA on uploaded image | Yes | Phase 10 `geochat_vqa`, `image_id` path | **PARTIAL** | Automated with `development` mock; architecture complete | Production demo with `geochat_service` on real upload | **16 — validation** |
| RS-VLM = `MBZUAI/geochat-7B` (not generic LLM) | Yes | Adapter + service hard-code model id | **PASS** (architecture) | Config, schemas, service README | GPU E2E on upload | **16 — validation** |
| Second single-image capability | Yes | Phase 11 scene **caption** (`single_image_caption`) | **PARTIAL** | Automated with mock; distinct from VQA routing | Production GeoChat caption via HTTP service | **16 — validation** |
| Text-guided **grounding** (bounding regions) | **UNKNOWN** (see §2) | Not implemented | **FAIL** if SIH requires both caption/grounding **and** VQA; **OPTIONAL** if SIH allows caption OR grounding | `AGENTS.md` Phase 15+; Phase 9A research note | Grounding tool + result schema + GUI | **17+** (if mandatory) |
| Real GeoChat inference (not mock) in production | Yes (for demo) | Phase 14 HTTP service + adapter; `GEOCHAT_VQA_PROVIDER=geochat_service` | **NOT VALIDATED** | Colab T4 smoke (Phase 9B); fake HTTP tests (Phase 14); `GEOCHAT_REAL_SERVICE_TEST` skipped in CI | Deploy GPU service; run acceptance with `geochat_service` | **16 — validation** |
| Standalone GeoChat HTTP service | Yes (Phase 14) | `services/geochat/` FastAPI, byte transfer | **PASS** (architecture) | 6 service tests; 16 backend adapter tests | T4 deployment + smoke artifact | **16 — validation** |

### D. Bi-temporal change (upload path)

| Requirement | Mandatory? | Current implementation | Status | Evidence | Missing work | Next phase |
|-------------|------------|------------------------|--------|----------|--------------|------------|
| Two-date upload pair analysis | Yes | `earlier_image_id` + `later_image_id` | **PASS** | Phase 12 tests + E2E | — | — |
| Temporal validation (order, acquisition dates) | Yes | `validate_bi_temporal(require_acquisition_dates=True)` | **PASS** | Phase 12 test 2 (reversed order rejected) | — | — |
| Change detection on upload pair | Yes | `detect_change` via `DeterministicChangeDetector` bridge | **PARTIAL** | Regions on map in dev; not real raster CVA | Real CVA on uploaded GeoTIFF (or EE bridge) | **18+** |
| Change understanding / change-VQA summary | Yes | `change_understanding` tool (template from CVA evidence) | **PARTIAL** | Query-aware summary; not RS-VLM | Optional RS-VLM change-VQA (explicitly out of scope in acceptance doc) | **OPTIONAL** |
| Spatial change evidence on map | Yes | CVA regions in `AnalysisResult.evidence` | **PARTIAL** | Deterministic polygons, not validated on real change | Real-data validation | **Validation** |

### E. Cross-modal optical + SAR (upload path)

| Requirement | Mandatory? | Current implementation | Status | Evidence | Missing work | Next phase |
|-------------|------------|------------------------|--------|----------|--------------|------------|
| Optical + SAR pair (same area) | Yes | `optical_image_id` + `sar_image_id` | **PASS** | Phase 13 tests 1–4 | — | — |
| Reject optical+optical, SAR+SAR | Yes | `validate_optical_sar_pair()` | **PASS** | Phase 13 tests 2–3 | — | — |
| Cross-modal planner intent | Yes | `cross_modal_optical_sar` | **PASS** | Phase 13 tests 8–9 | — | — |
| Optical specialist + SAR specialist | Yes | `optical_analysis`, `sar_analysis` (development) | **PARTIAL** | Trace + labeled mock analyzers | Real optical/SAR upload specialists | **19+** |
| Explicit fusion stage (not concatenation) | Yes | `cross_modal_fusion` policy `uploaded_cross_modal_fusion_v1.0.0` | **PASS** (architecture) | Phase 13 tests 10–11 | Real fusion on real modalities | **19+** |
| GUI: optical, SAR, joint analysis, trace | Yes | Cross-modal composer + inspector sections | **PASS** | `cross-modal.spec.ts` | — | — |
| Verified co-registration when claimed | Yes | `verified_benchmark` only with matching `benchmark_pair_id` | **PASS** (policy) | Phase 13 test 7 | Real benchmark pair dataset demo | **Validation** |

### F. Explicitly non-mandatory (per repo)

| Requirement | Mandatory? | Status | Evidence |
|-------------|------------|--------|----------|
| RS-VLM fine-tuning / LoRA adaptation | No | **OPTIONAL** | `experiments/phase9b_geochat_adaptation/` research only |
| Change-VQA with RS-VLM | No | **OPTIONAL** | `SIH_ACCEPTANCE_BI_TEMPORAL_CHANGE.md` “Not in scope” |
| Reference-mask / benchmark evaluation (IoU, etc.) | No | **OPTIONAL** | Not implemented; experiments evaluation scaffolding only |
| PostgreSQL / PostGIS persistence | No | **OPTIONAL** | `AGENTS.md` Phase 15+ |
| Authentication / multi-user | No | **OPTIONAL** | Not implemented |
| PDF / report generation | No | **OPTIONAL** | Not implemented |
| Optical-SAR fusion on Earth Engine catalog | No (upload track) | **PASS** (catalog) | Phase 5 `fuse_evidence` for EE path — separate from upload cross-modal |

---

## 4. Current evidence (by validation layer)

### 4.1 Architecture implemented

- Upload input schemas and validation (`backend/app/schemas/input.py`, `compatibility.py`)
- Four upload analysis pipelines in `query_controller.py`
- Planner intents and tool registry (`schemas/planning.py`, `planner/`)
- GeoChat adapter abstraction (`adapters/rsvlm/`)
- Standalone service (`services/geochat/`)
- Frontend composer modes and inspector (`QueryComposer.tsx`, `EvidenceInspector.tsx`)

### 4.2 Automated tests passed (2026-08-26 run)

| Suite | Result |
|-------|--------|
| Backend pytest | **241 passed**, 3 skipped |
| GeoChat service pytest | **6 passed** |
| Frontend Vitest | **9 passed** |
| Playwright E2E | **8 passed** |
| Frontend production build | **Success** |

Skipped backend tests: malformed-raster upload rejects at ingest (2), real GPU integration (1, `GEOCHAT_REAL_SERVICE_TEST`).

### 4.3 Real satellite imagery validated

| Item | Status |
|------|--------|
| Real Sentinel-2 GeoChat VQA (Colab T4, 504×504 PNG) | **VALIDATED** — `experiments/phase9b_geochat/`, Phase 9B notebook |
| Real GeoChat on uploaded GeoTIFF via app + HTTP service | **NOT VALIDATED** |
| Real uploaded-raster CVA | **NOT VALIDATED** |
| Real optical+SAR fusion on uploads | **NOT VALIDATED** |
| Real co-registered optical+SAR benchmark pair | **NOT VALIDATED** |
| Fine-tuned RS-VLM | **NOT IMPLEMENTED** |
| Grounding | **NOT IMPLEMENTED** |
| Reference-mask evaluation | **NOT IMPLEMENTED** |

### 4.4 Production deployment validated

| Item | Status |
|------|--------|
| GeoChat GPU service deployed and health-checked | **NOT VALIDATED** |
| Backend `GEOCHAT_VQA_PROVIDER=geochat_service` E2E on upload | **NOT VALIDATED** |
| Colab smoke test | **VALIDATED** (research environment only — not production service) |

---

## 5. Missing mandatory capabilities

Interpreted strictly for an SIH **production demonstration** (real model, real imagery, honest claims):

1. **Production GeoChat path on uploads** — architecture complete; no recorded E2E run with `geochat_service` on a user GeoTIFF through SatQuery GUI/API.
2. **Real change detection on uploaded bi-temporal pairs** — workflow complete; specialist is `DeterministicChangeDetector`, not validated on real rasters.
3. **Real cross-modal specialists on uploads** — workflow and fusion stage complete; optical/SAR analyzers are development mocks.
4. **Grounding** — if the official SIH statement requires it alongside VQA (Phase 9A research note), this is an open **FAIL**; if “caption OR grounding” suffices, caption is done and grounding remains optional.

---

## 6. Real-data validation gaps

| Gap | Risk if unaddressed | Recommended action |
|-----|---------------------|-------------------|
| No HTTP service E2E on upload | Judges see development mock labels | Deploy `services/geochat` on T4; run `docs/SIH_ACCEPTANCE_SINGLE_IMAGE_VQA.md` with `geochat_service` |
| Colab ≠ production service | Smoke test does not prove deployed adapter path | Run `scripts/run_real_validation.py` + `GEOCHAT_REAL_SERVICE_TEST=true` |
| Upload CVA is deterministic | Change regions are not from real spectral analysis | Wire upload bridge to real CVA or document as demo limitation |
| Cross-modal mocks | “Fusion” does not use real optical/SAR signal | Wire EE or upload-capable SAR/optical analyzers; or demo with explicit dev labels |
| Co-registration | Overlap ≠ co-register | Use audited benchmark pair only when dataset provides it |

---

## 7. Recommended implementation order

| Priority | Phase | Work | Type |
|----------|-------|------|------|
| **P0** | 16 | Deploy GeoChat HTTP service on T4; validate VQA + caption on uploaded GeoTIFF; save `validation_artifacts/` | **Validation only** |
| **P1** | 17 | Clarify SIH grounding requirement with official statement; implement grounding only if mandatory | Feature or skip |
| **P2** | 18 | Real CVA on uploaded bi-temporal GeoTIFF (minimal: raster read + EE-free CVA) | Feature |
| **P3** | 19 | Real upload-path optical/SAR specialists + fusion (or EE catalog bridge with honest scope) | Feature |
| **P4** | 20+ | Change-VQA with RS-VLM, fine-tuning, benchmark eval, auth, DB | Optional / post-SIH |

---

## 8. Explicit “DO NOT IMPLEMENT YET” list

Do **not** start these until P0 validation is complete and SIH grounding scope is confirmed:

- Text-guided region **grounding** (unless confirmed mandatory)
- RS-VLM **change-VQA** (distinct from template `change_understanding`)
- **LoRA / fine-tuning** pipeline in production
- **Reference-mask** benchmark evaluation harness
- **PostgreSQL / PostGIS** session and imagery catalog
- **Authentication** and multi-tenancy
- **Report PDF** generation
- Replacing development upload specialists **silently** without provenance labels
- Claiming **verified co-registration** without benchmark metadata
- Using **generic OpenAI/LLM** as substitute for GeoChat

---

## 9. Test status (verified 2026-08-26)

```
Backend pytest:     241 passed, 3 skipped
GeoChat service:      6 passed
Frontend Vitest:      9 passed
Playwright E2E:       8 passed
Frontend build:     success
```

No GPU inference was run for this audit.

---

## 10. Closing checklist

| SIH upload mandatory workflow | Architecture | Automated tests | Real-data demo |
|------------------------------|--------------|-----------------|----------------|
| Input foundation | ✅ | ✅ | N/A |
| Single-image VQA | ✅ | ✅ (mock) | ❌ |
| Single-image caption | ✅ | ✅ (mock) | ❌ |
| Bi-temporal change | ✅ | ✅ (dev CVA) | ❌ |
| Cross-modal optical+SAR | ✅ | ✅ (dev specialists) | ❌ |
| GeoChat HTTP service | ✅ | ✅ (fake HTTP) | ❌ |
| Agentic trace + GUI | ✅ | ✅ | N/A |

---

## MANDATORY REQUIREMENTS REMAINING:

- **Production demonstration** of single-image VQA and scene caption using **real `MBZUAI/geochat-7B`** via deployed `geochat_service` on uploaded GeoTIFF (**NOT VALIDATED**)
- **Real** bi-temporal change detection on uploaded raster pairs (currently development CVA only) (**NOT VALIDATED**)
- **Real** optical and SAR analysis + fusion on uploaded cross-modal pairs (currently development mocks) (**NOT VALIDATED**)
- **Grounding** — **FAIL / UNKNOWN** until official SIH statement is confirmed (research notes say mandatory; implementation chose caption instead)

## OPTIONAL FEATURES:

- Text-guided grounding (if not required in lieu of caption)
- Change-VQA with RS-VLM
- RS-VLM fine-tuning / LoRA on BigEarthNet
- Reference-mask benchmark evaluation (IoU, etc.)
- PostgreSQL/PostGIS, authentication, report generation
- Earth Engine catalog extensions beyond current Phase 1–7 scope

## VALIDATION ONLY:

- Deploy `services/geochat` on T4 GPU host
- Run `GEOCHAT_REAL_SERVICE_TEST=true` integration test
- Run all four `docs/SIH_ACCEPTANCE_*.md` procedures with `GEOCHAT_VQA_PROVIDER=geochat_service`
- Save artifacts to `services/geochat/validation_artifacts/` (gitignored)
- Optional: real CVA / cross-modal demos with explicit provenance labels

## DO NOT IMPLEMENT YET:

- Grounding, change-VQA, fine-tuning, benchmark eval, auth, DB, reports (until P0 validation + scope confirmation)
- Silent fallback from `geochat_service` to development mock in production
- False co-registration or calibrated confidence claims without evidence

---

*This audit does not claim the entire SIH problem statement is complete. It records repository state after Phases 8–14 only.*
