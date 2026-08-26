# SatQuery AI — Agent Guide

## Principles

1. **Backend is source of truth.** Frontend consumes API contracts only.
2. **Stable interfaces.** Imagery, change detection, VLM, and object detectors live behind adapters.
3. **Evidence engine validates metrics.** Never invent numbers in the answer layer.
4. **DESIGN.md is authoritative** for all UI work.
5. **₹0 budget.** No paid APIs. Open-source and Earth Engine (when credentialed) only.

## Repository layout

```
backend/app/
  schemas/domain.py     # Pydantic contracts
  tools/                # Typed tool registry
  adapters/             # External providers (imagery, change detection)
  evidence/             # Evidence engine
  services/             # Query controller, session store, answer engine
  api/routes/           # FastAPI endpoints

frontend/src/
  types/domain.ts       # TypeScript mirrors (no business logic)
  lib/api.ts            # API client
  components/           # Workstation UI

experiments/            # ML research only — not imported by app
```

## Vertical slice (Phase 1)

AOI + dates + query → `POST /api/v1/query/submit` → fetch_imagery → detect_change → generate_evidence → AnalysisResult → map + trace + inspector.

## What is mock

- `DevelopmentImageryProvider` — deterministic scene metadata, not Earth Engine
- `DeterministicChangeDetector` — seeded polygons, not CVA/ChangeFormer
- Answer engine — template from evidence, not an LLM

## Phase 2A (implemented)

- `EarthEngineProvider` — real Sentinel-2 metadata via Google Earth Engine (`COPERNICUS/S2_SR_HARMONIZED`)
- Deterministic anchor scene selection (policy v1.0.0)
- `ImageryScene.platform_id` carries EE asset path for downstream analysis

## Phase 2B (implemented)

- `EarthEngineChangeDetector` — deterministic Sentinel-2 CVA via Earth Engine
- QA60 + SCL cloud masking, multispectral magnitude, thresholded vectorization
- `DeterministicChangeDetector` retained for development mode

## Phase 2C (implemented — plumbing)

- `SemanticAnalyzer` interface + `DevelopmentSemanticAnalyzer`
- `analyze_semantics` tool step (profile-gated by construction keywords)
- Evidence fusion (`evidence/fusion.py`) — CVA + semantic, never conflated
- `SEMANTIC_ANALYZER=development|earth_engine` (earth_engine = Phase 3B)

## Phase 3B (implemented)

- `EarthEngineDynamicWorldBuiltAnalyzer` — Dynamic World `built` band via `GOOGLE/DYNAMICWORLD/V1`
- Policy `dynamic_world_built_construction_v1` v1.0.0 (delta ≥ 0.15, overlap ≥ 0.30, area ≥ 2000 m²)
- Temporal windows anchored to Sentinel-2 acquisition dates (0d before, 7d after)
- `SEMANTIC_ANALYZER=earth_engine` instantiates production analyzer (no silent fallback)

## Phase 4 (implemented)

- `EarthEngineProvider` — Sentinel-1 GRD via `COPERNICUS/S1_GRD` (VV/VH, IW mode, orbit-aware anchor selection)
- `EarthEngineSARChangeDetector` — deterministic SAR backscatter change (speckle filter + dB differencing) **v1.1.0**
- `SAR_CHANGE_DETECTOR=earth_engine` required for Sentinel-1 (no silent fallback)
- SAR evidence typed `sar_change` with `evidence_modality: sar` — no semantic flood/construction/damage claims

## Phase 5 (implemented)

- Multimodal evidence fusion (`evidence/multimodal_fusion.py` policy v1.0.0)
- Polygon geometry intersection for overlap fractions
- `fuse_evidence` + `detect_sar_change` pipeline steps
- Query profile gating: construction → semantic, radar/SAR keywords → SAR
- Conservative fused confidence: `min(cva, semantic, sar)` where applicable

## Phase 6 (implemented)

- Constrained agentic query planning — NL → validated `QueryAnalysisPlan` (`schemas/planning.py`)
- Intents: `spectral_change`, `construction`, `radar_change`, `multimodal_comparison`
- Planner tools only: `fetch_imagery`, `detect_change`, `analyze_semantics`, `detect_sar_change`, `fuse_evidence`, `generate_evidence`
- `QUERY_PLANNER=deterministic|llm` — deterministic keyword fallback when LLM unavailable or invalid
- Optional `OPENAI_API_KEY` + structured JSON output; invalid plans rejected (no silent fabrication)
- `plan_query` trace step exposes planner, intent, tools, modalities, version (no chain-of-thought)
- Answer engine unchanged — evidence from specialist tools only

## Phase 7 (implemented)

- Map-first frontend workstation per DESIGN.md
- AOI drawing, ISO dates, query composer, execution trace, evidence inspector
- Real API via `POST /api/v1/query/submit` with URL state

## Phase 8 (implemented — input foundation only)

- **Earth Engine path (unchanged):** AOI + dates → `EarthEngineProvider` / `DevelopmentImageryProvider` → CVA/DW/SAR/fusion
- **Upload path (new):** user file → `UploadedImageryProvider` → validated `ImageInput` metadata in local storage
- Schemas: `schemas/input.py` — `ImageInput`, `AnalysisInputType`, bi-temporal and optical/SAR pair contracts
- `ImageInput` ≠ `ImageryScene` (user upload vs catalog observation)
- `POST /api/v1/imagery/upload`, `GET /api/v1/imagery/{image_id}`, `POST /api/v1/imagery/validate-input`
- Compatibility checks: overlap, CRS warnings, dimensions, modality rules (no co-registration claims)
- Config: `UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB`
- **Not implemented (pre-Phase 10):** VQA, grounding, captioning, change-VQA, RS-VLM, frontend upload UI

## Phase 9 (experiments only — not imported by app)

- GeoChat-7B Colab smoke test (`experiments/phase9b_geochat/`) — verified 8-bit T4 load + genuine inference
- Adaptation research (`experiments/phase9b_geochat_adaptation/`) — interface sketches only

## Phase 10 (implemented — SIH mandatory single-image VQA)

- **Intent:** `single_image_vqa` via agentic planner when `QueryRequest.image_id` is set
- **Specialist:** `tools/single_image/geochat_vqa.py` → `adapters/rsvlm/` (`development` mock | `geochat_service` HTTP GPU)
- **Model:** `MBZUAI/geochat-7B` (real inference requires `GEOCHAT_VQA_PROVIDER=geochat_service` + GPU service URL)
- **API:** `POST /api/v1/query/submit` accepts `{ query, image_id }` alongside existing AOI/date catalog mode
- **Upload:** `POST /api/v1/imagery/upload` + frontend upload/VQA composer mode
- **Formats:** GeoTIFF/TIFF (production); PNG/JPEG only with `benchmark_dataset=true`
- **Trace:** `plan_query` → `input_validation` → `geochat_vqa` → `generate_evidence`
- **Evidence:** VQA returns narrative answer + model provenance in `AnalysisResult.vqa`; no fabricated spatial regions or confidence
- Config: `GEOCHAT_VQA_PROVIDER`, `GEOCHAT_SERVICE_URL`, `GEOCHAT_MODEL_ID`
- **Not implemented:** change-VQA, grounding, fine-tuning, reports, auth

## Phase 11 (implemented — SIH mandatory single-image scene description)

- **Intent:** `single_image_caption` when `image_id` is set and query requests general scene description
- **Specialist:** `tools/single_image/geochat_caption.py` → same `adapters/rsvlm/` provider (no duplicate GeoChat client)
- **Distinction:** VQA = specific question (`What land-cover types are visible?`); caption = scene description (`Describe this satellite scene.`)
- **API:** same `POST /api/v1/query/submit` with `{ query, image_id }`; planner selects VQA vs caption
- **Result:** `AnalysisResult.caption` with `task: single_image_caption`, `description`, model/provider provenance
- **Trace:** `input_validation` → `plan_query` → `geochat_caption` → `generate_evidence`
- **Evidence:** no fabricated spatial regions, bounding boxes, or confidence
- Acceptance: `docs/SIH_ACCEPTANCE_SINGLE_IMAGE_SCENE_DESCRIPTION.md`

## Phase 12 (implemented — SIH mandatory bi-temporal change)

- **Intent:** `bi_temporal_change_vqa` when `earlier_image_id` + `later_image_id` are set
- **Validation:** Phase 8 `validate_bi_temporal()` with required acquisition dates
- **CVA:** Reuses `DeterministicChangeDetector` via `detect_change` (upload bridge — no CVA rewrite)
- **Understanding:** `change_understanding` tool — query-aware summary from CVA evidence
- **API:** `POST /api/v1/query/submit` with `{ query, earlier_image_id, later_image_id }`
- **Upload:** `acquisition_datetime` form field on `POST /api/v1/imagery/upload`
- **Trace:** `input_validation` → `plan_query` → `detect_change` → `change_understanding` → `generate_evidence`
- **Evidence:** Real CVA regions on map; no fabricated masks
- Acceptance: `docs/SIH_ACCEPTANCE_BI_TEMPORAL_CHANGE.md`

## Phase 13 (implemented — SIH mandatory cross-modal optical + SAR)

- **Intent:** `cross_modal_optical_sar` when `optical_image_id` + `sar_image_id` are set
- **Validation:** Phase 8 `validate_optical_sar_pair()` — modality, overlap, honest co-registration status
- **Co-registration:** `verified_benchmark` only when both images uploaded with matching `benchmark_pair_id` via audited `benchmark_dataset` path
- **Specialists:** `optical_analysis`, `sar_analysis` (development upload adapters)
- **Fusion:** `cross_modal_fusion` — explicit joint stage (`uploaded_cross_modal_fusion_v1.0.0`), not answer concatenation
- **API:** `POST /api/v1/query/submit` with `{ query, optical_image_id, sar_image_id }`
- **Upload:** optional `co_registered_benchmark_pair` + `benchmark_pair_id` (honored only with `benchmark_dataset=true`)
- **Trace:** `input_validation` → `plan_query` → `optical_analysis` → `sar_analysis` → `cross_modal_fusion` → `generate_evidence`
- **Result:** `AnalysisResult.cross_modal` with optical/SAR/fused summaries and co-registration provenance
- Acceptance: `docs/SIH_ACCEPTANCE_OPTICAL_SAR.md`

## Phase 14 (implemented — real GeoChat GPU service integration)

- **Service:** `services/geochat/` — standalone FastAPI hosting `MBZUAI/geochat-7B` (Phase 9B 8-bit T4 load path)
- **API:** `GET /health`, `POST /v1/vqa`, `POST /v1/caption` — image bytes + metadata (no filesystem paths)
- **Backend adapter:** `GeoChatServiceVLM` sends base64 raster bytes via `GEOCHAT_VQA_PROVIDER=geochat_service`
- **Development:** `GEOCHAT_VQA_PROVIDER=development` unchanged — deterministic mock, no silent fallback in production mode
- **Config:** `GEOCHAT_SERVICE_URL`, `GEOCHAT_MODEL_ID`, `GEOCHAT_SERVICE_TIMEOUT_S`
- **Trace:** `geochat_vqa` / `geochat_caption` with `provider=geochat_service`, `model=MBZUAI/geochat-7B`
- **Tests:** `backend/tests/test_phase14_geochat_service.py` (fake HTTP service); real GPU test gated by `GEOCHAT_REAL_SERVICE_TEST=true`

## Phase 15+ (not started)

- Grounding, change-VQA with RS-VLM
- PostgreSQL/PostGIS, auth, reports
