# SatQuery AI

Evidence-driven multimodal satellite intelligence platform for Smart India Hackathon 2026.

## Architecture

- **Backend:** FastAPI query controller, typed tool registry, evidence engine, adapter boundaries
- **Frontend:** Next.js + MapLibre workstation (see `DESIGN.md`)
- **Contracts:** Pydantic schemas (`backend/app/schemas/domain.py`) mirrored in TypeScript (`frontend/src/types/domain.ts`)

## Quick start

### Backend

Requires **Python 3.11+**.

```bash
cd backend
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic pydantic-settings httpx pytest pytest-asyncio
PYTHONPATH=. pytest
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
SATQUERY_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000. API requests proxy through Next.js to the backend (`next.config.js` rewrites).

## APIs (Phase 1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health and imagery provider mode |
| POST | `/api/v1/imagery/fetch` | Fetch catalog imagery metadata (Earth Engine / development) |
| POST | `/api/v1/imagery/upload` | Upload and validate user-provided GeoTIFF/TIFF (PNG/JPEG for benchmark datasets) |
| GET | `/api/v1/imagery/{image_id}` | Retrieve normalized upload metadata |
| POST | `/api/v1/imagery/validate-input` | Validate single / bi-temporal / optical+SAR input compatibility |
| POST | `/api/v1/query/submit` | Run full analysis pipeline |
| GET | `/api/v1/query/{session_id}/trace` | Execution trace |
| GET | `/api/v1/query/{session_id}/result` | Stored analysis result |
| POST | `/api/v1/analysis/detect-change` | Change detection only |

## Development vs production data

Default: `IMAGERY_PROVIDER=development`. Responses include `mode: "development"` and an explicit disclaimer message.

For real Sentinel-2 imagery via Google Earth Engine, set `IMAGERY_PROVIDER=earth_engine` (see below).

## Input paths (Phase 8)

Upload + validate user imagery (`POST /api/v1/imagery/upload`). See `backend/app/schemas/input.py`.

## Single-image VQA (Phase 10 — SIH mandatory)

- Upload one GeoTIFF/TIFF (or benchmark PNG/JPEG) → ask a natural-language question → GeoChat-7B specialist
- Workstation **Upload image** mode or `POST /api/v1/query/submit` with `{ query, image_id }`
- Real inference: `GEOCHAT_VQA_PROVIDER=geochat_service` + GPU service (Phase 9B reference). Local dev uses labeled `development` mock.
- Acceptance procedure: `docs/SIH_ACCEPTANCE_SINGLE_IMAGE_VQA.md`

## Single-image scene description (Phase 11 — SIH mandatory)

- Same upload path; planner routes scene-description queries to `single_image_caption` → `geochat_caption`
- Example query: `Describe this satellite scene.`
- Structured result in `AnalysisResult.caption` (distinct from VQA `answer`)
- Acceptance procedure: `docs/SIH_ACCEPTANCE_SINGLE_IMAGE_SCENE_DESCRIPTION.md`

## Bi-temporal change analysis (Phase 12 — SIH mandatory)

- Upload two GeoTIFF/TIFF images with `acquisition_datetime` → ask a change question
- Workstation **Temporal pair** mode or `POST /api/v1/query/submit` with `{ query, earlier_image_id, later_image_id }`
- Reuses existing deterministic CVA on uploaded pair overlap (development path)
- Acceptance procedure: `docs/SIH_ACCEPTANCE_BI_TEMPORAL_CHANGE.md`

**Earth Engine path (unchanged):** AOI + dates → catalog provider → CVA / Dynamic World / SAR / fusion.

**Upload path:** user file → local storage → `ImageInput` validation → VQA or scene caption via GeoChat RS-VLM adapter. Grounding and change-VQA are **not** implemented yet.

Upload config: `UPLOAD_DIR` (default `data/uploads`), `MAX_UPLOAD_SIZE_MB` (default `256`).

## Google Earth Engine setup (Phase 2A)

### Prerequisites

1. [Register for Earth Engine access](https://signup.earthengine.google.com/)
2. A Google Cloud project with Earth Engine enabled
3. Python 3.11+

### Install

```bash
pip install earthengine-api
# or: pip install -e ".[earth_engine]"
```

### Authenticate (choose one)

**Option A — interactive (local development):**

```bash
earthengine authenticate
```

**Option B — service account (recommended for servers):**

1. Create a service account in Google Cloud Console
2. Register it for Earth Engine access
3. Download the JSON key (never commit it)
4. Set in `.env`:

```
IMAGERY_PROVIDER=earth_engine
EARTH_ENGINE_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

**Option C — Application Default Credentials:**

```bash
gcloud auth application-default login
```

### Configure SatQuery

```bash
# backend/.env
IMAGERY_PROVIDER=earth_engine
CHANGE_DETECTOR=earth_engine
EARTH_ENGINE_PROJECT=your-gcp-project-id
```

Restart the backend. Health endpoint will report `imagery_provider: "earth_engine"`, `change_detector: "earth_engine"`, and `mode: "production"`.

### Scene selection policy

Earth Engine provider uses deterministic anchor selection (policy v1.0.0):

1. Filter `COPERNICUS/S2_SR_HARMONIZED` to AOI bounds and date range
2. Filter `CLOUDY_PIXEL_PERCENTAGE < cloud_cover_max` (default 30%)
3. Select start-anchor scene closest to `start_date` (tie: lowest cloud, then scene ID)
4. Select end-anchor scene closest to `end_date` (same tie-breaks)
5. Return unique scenes sorted by acquisition date

`ImageryResult.platform_id` on each scene carries the EE asset path for downstream change detection.

### Change detection (Earth Engine CVA)

When `CHANGE_DETECTOR=earth_engine` (default follows `IMAGERY_PROVIDER`):

1. Load before/after scenes by `platform_id` from the imagery pipeline
2. Apply QA60 + SCL cloud/shadow masking
3. Compute Euclidean change magnitude across bands B2, B3, B4, B8, B11, B12
4. Threshold at fixed magnitude 800 (SR scale, policy v1.0.0)
5. Vectorize connected components at 10 m; filter regions &lt; 500 m²
6. Confidence derived from measured mean magnitude above threshold (not invented)

`DeterministicChangeDetector` remains available for development mode.

### Without Earth Engine credentials

Keep `IMAGERY_PROVIDER=development`. The app runs with deterministic demo data clearly labeled as development mode. It never silently falls back when `earth_engine` is explicitly configured.

## Tests

```bash
cd backend && pytest
cd frontend && npm test
cd frontend && npm run test:e2e  # requires backend + frontend running
```

## Documentation

- `DESIGN.md` — authoritative UI specification
- `AGENTS.md` — agent implementation guide
