# Phase 6 — Real-Data Evaluation

Evaluation code is **separate from production detectors**. It runs curated cases through the same `QueryController` API used in production and records structured outcomes.

## Requirements for live Earth Engine runs

```bash
export IMAGERY_PROVIDER=earth_engine
export CHANGE_DETECTOR=earth_engine
export SEMANTIC_ANALYZER=earth_engine   # required for urban/infrastructure construction path
export EARTH_ENGINE_PROJECT=your-gcp-project
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json  # or: earthengine authenticate
export EE_REAL_EVALUATION=true
```

## Run evaluation suite

```bash
cd backend
python scripts/run_evaluation.py --output evaluation/reports/latest.json
```

Without `EE_REAL_EVALUATION=true`, the script records configuration and exits (unit tests use mocks).

## Cases

See `evaluation/cases/catalog_cases.json` — five qualitative catalog cases aligned to competition domains.

## Metrics

- **Qualitative:** `evaluation_type=qualitative` — no IoU/F1 reported
- **Quantitative:** requires `ground_truth.geometry` on the case; computed in `evaluation/metrics.py`

## Significance / threshold documentation

| Threshold | Value | Classification |
|-----------|-------|----------------|
| CVA magnitude | 1000 SR Euclidean | Policy v1.1.0 — empirically raised from 800 |
| Min region area | 2000 m² | Policy v1.1.0 — reduces speckle polygons |
| Max regions | 50 | Policy cap — may truncate large events |
| DW built delta | ≥ 0.15 | Benchmark-informed semantic policy |
| DW overlap | ≥ 0.30 | Geometry intersection policy |
| Domain significance | 0.4·area + 0.35·conf + 0.25·support | Phase 5B policy — not benchmark-tuned |

## False-positive modes (documented, not auto-suppressed)

- Vegetation seasonality / harvest cycles (deforestation, mining)
- Cloud/shadow contamination (all optical)
- Water seasonality (water shrinkage)
- Bare soil ↔ mining ambiguity (mining)
- Built-up ↔ infrastructure ambiguity (infrastructure)
- Registration differences between anchor scenes (all catalog CVA)
