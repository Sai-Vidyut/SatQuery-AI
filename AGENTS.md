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

## Phase 7+ (not started)

- Learned change detectors (ChangeFormer, BIT-CD) behind `ChangeDetector`
- RS-VLM behind `RSVLM` interface
- PostgreSQL/PostGIS, auth, reports
