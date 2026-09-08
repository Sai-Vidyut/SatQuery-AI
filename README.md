# SatQuery AI

Ask questions about satellite imagery in plain language and get evidence-backed answers you can inspect on the map.

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Usage](#usage)
- [Team](#team)

## Overview

SatQuery AI is a map-first geospatial intelligence workstation. Analysts, researchers, and demo operators can select an area of interest or upload imagery, ask a natural-language question, and receive a structured answer backed by traceable evidence—not a black-box summary.

The platform supports multiple analysis paths: catalog-based change detection over an AOI and date range (via Google Earth Engine when credentialed, or deterministic development fixtures locally), single-image visual question answering and scene description on uploaded GeoTIFFs, bi-temporal before/after change analysis on image pairs, and joint optical + SAR cross-modal analysis.

Each run produces an execution trace, a narrative answer, and—where applicable—map-linked evidence regions with confidence metrics you can explore in the Results panel.

## Features

- **Natural language querying (AOI + dates)** — Draw an area of interest, pick a date range, and ask questions about spectral change, construction, or radar-related patterns.
- **Single-image upload (VQA & captioning)** — Upload a GeoTIFF/TIFF and ask a specific question, or request a general scene description.
- **Temporal pair comparison** — Upload before/after images to detect and summarize change between two acquisition dates.
- **Cross-modal analysis (optical + SAR)** — Upload optical and SAR imagery together for joint analysis and fused summaries.
- **Evidence-backed results** — Answers include an execution trace, map-linked evidence regions, and per-region confidence where the pipeline produces them.
- **Development mode (local / offline-friendly)** — Default `IMAGERY_PROVIDER=development` uses deterministic fixtures with clear labeling—no Earth Engine credentials required to run the full workstation flow locally.

## Tech stack

### Frontend

- [Next.js](https://nextjs.org/) 15 (App Router)
- [React](https://react.dev/) 19
- [TypeScript](https://www.typescriptlang.org/) 5.7
- [Tailwind CSS](https://tailwindcss.com/) 4
- [MapLibre GL JS](https://maplibre.org/) 4.7
- [@phosphor-icons/react](https://phosphoricons.com/) 2.1

### Backend

- [Python](https://www.python.org/) 3.11+
- [FastAPI](https://fastapi.tiangolo.com/) 0.115+
- [Uvicorn](https://www.uvicorn.org/)
- [Pydantic](https://docs.pydantic.dev/) 2.10+
- Optional: [Google Earth Engine Python API](https://developers.google.com/earth-engine) (`earth_engine` extra)

### Services

- **GeoChat inference service** (`services/geochat/`) — Standalone FastAPI service for GPU-backed single-image VQA and captioning (optional; local development uses a labeled mock provider).

## Project structure

```
SatQuery-AI/
├── backend/       # FastAPI API, evidence engine, imagery/change adapters, tests
├── frontend/      # Next.js map workstation UI
├── services/      # Standalone GeoChat GPU inference service
├── docs/          # Acceptance procedures and phase documentation
└── experiments/   # ML research and smoke tests (not imported by the app)
```

## Getting started

### Prerequisites

- **Node.js** 22+ (matches `@types/node` in the frontend)
- **Python** 3.11+ (required by `backend/pyproject.toml`)
- **npm** (bundled with Node.js)

### Installation

```bash
git clone https://github.com/Sai-Vidyut/SatQuery-AI.git
cd SatQuery-AI
```

**Backend**

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
```

**Frontend**

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

### Environment variables

Copy the example files and set values locally. **Never commit real secrets.**

**Backend** (`backend/.env`) — names only:

| Variable | Purpose |
|----------|---------|
| `IMAGERY_PROVIDER` | `development` (default) or `earth_engine` |
| `CHANGE_DETECTOR` | Override change detector provider |
| `SAR_CHANGE_DETECTOR` | Override SAR change detector provider |
| `SEMANTIC_ANALYZER` | `development` or `earth_engine` |
| `EARTH_ENGINE_PROJECT` | Google Cloud project ID (Earth Engine) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON |
| `UPLOAD_DIR` | Local upload storage directory |
| `MAX_UPLOAD_SIZE_MB` | Max upload file size |
| `GEOCHAT_VQA_PROVIDER` | `development` or `geochat_service` |
| `GEOCHAT_SERVICE_URL` | URL of the GeoChat GPU service |
| `GEOCHAT_MODEL_ID` | Remote-sensing VLM model identifier |
| `GEOCHAT_SERVICE_TIMEOUT_S` | GeoChat HTTP timeout (seconds) |
| `QUERY_PLANNER` | `deterministic` or `llm` |
| `OPENAI_API_KEY` | Optional, for LLM query planner |
| `OPENAI_MODEL` | OpenAI model for planner |

**Frontend** (`frontend/.env.local`):

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL (empty uses Next.js rewrites) |
| `SATQUERY_BACKEND_URL` | Backend URL for Next.js dev rewrites (default `http://127.0.0.1:8000`) |

### Run in development

**Terminal 1 — backend**

```bash
cd backend
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

**Terminal 2 — frontend**

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API requests proxy to the backend via `next.config.js` rewrites.

### Development mode (no live satellite catalog)

Default backend config uses deterministic development adapters:

```bash
# backend/.env
IMAGERY_PROVIDER=development
GEOCHAT_VQA_PROVIDER=development
```

Responses are clearly labeled as development or mock data. For real Sentinel-2 catalog analysis, install the Earth Engine extra and configure credentials:

```bash
pip install -e ".[earth_engine]"
# Then set IMAGERY_PROVIDER=earth_engine and authenticate Earth Engine
```

See the existing Earth Engine section in this repository's docs and `backend/.env.example` for authentication options.

### Optional: GeoChat GPU service

For production single-image VQA/captioning with a GPU host, see `services/geochat/README.md`. Point the backend at the service with `GEOCHAT_VQA_PROVIDER=geochat_service` and `GEOCHAT_SERVICE_URL`.

### Other commands

```bash
# Backend tests
cd backend && pytest

# Frontend unit tests
cd frontend && npm test

# Frontend E2E (requires backend + frontend running)
cd frontend && npm run test:e2e

# Production frontend build
cd frontend && npm run build && npm start
```

## Usage

1. **Open the workstation** at [http://localhost:3000](http://localhost:3000).
2. **Choose a mode** in the composer: **AOI + dates**, **Upload image**, **Temporal pair**, or **Cross-modal**.
3. **Provide inputs** — draw an AOI and set dates, or upload the required GeoTIFF/TIFF files (and acquisition dates for temporal pairs).
4. **Ask your question** in plain language (e.g. *Show me significant new construction* or *What changed between these two dates?*).
5. **Run analysis** and review the **Results** panel: execution trace, answer, evidence regions on the map, and region-level metrics when available.

## Team

Built at **SRMIST**:

| Name | Role |
|------|------|
| **Sai Vidyut C** | Backend & AI Systems Lead |
| **Josh Jiby** | Frontend & Product Experience Lead |
| **Fathima Rinaya** | Product Strategy & Communication Lead |

For deeper implementation notes, see `AGENTS.md` and `DESIGN.md` in this repository.
