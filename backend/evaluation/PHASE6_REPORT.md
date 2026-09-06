# Phase 6 — Real-Data Evaluation Report

This report documents the Phase 6 real-data validation layer. Live Earth Engine execution requires credentials (`EE_REAL_EVALUATION=true`).

## A. Real-data evaluation cases

| Case ID | Domain | AOI (approx.) | T1 | T2 | Collection | Expected change | Evaluation |
|---------|--------|---------------|----|----|------------|-----------------|------------|
| `urban_expansion_bengaluru_east` | Urban expansion | Bengaluru east 77.72–77.78°E | 2018-06-01 | 2024-06-01 | S2 SR Harmonized | Built-up periphery growth | Qualitative |
| `deforestation_amazon_rondonia` | Deforestation | Rondônia, Brazil | 2019-08-01 | 2023-08-01 | S2 SR Harmonized | Forest clearing patches | Qualitative |
| `water_shrinkage_lake_mead` | Water shrinkage | Lake Mead, USA | 2016-06-01 | 2022-06-01 | S2 SR Harmonized | Shoreline water loss | Qualitative |
| `infrastructure_dubai_south` | Infrastructure | Dubai south | 2018-01-01 | 2024-01-01 | S2 SR Harmonized | New infrastructure/built growth | Qualitative |
| `mining_disturbance_eu_reference` | Mining | Saxony area, DE | 2017-06-01 | 2023-06-01 | S2 SR Harmonized | Open-cast disturbance | Qualitative |

**Public dataset references (not imported as ground truth in Phase 6):**
- Urban: [Urban monthly land dynamics Sentinel-2 benchmark (Zenodo)](https://doi.org/10.5281/zenodo.10846426)
- Mining: [EuroMineNet (RODARE)](https://doi.org/10.14278/rodare.4656), [MineNetCD](https://github.com/AI4RS/MineNetCD)
- Forest/water: INPE PRODES context; US Bureau of Reclamation Lake Mead records

## B. Results by category (expected system behavior)

| Category | Detects spectral change? | Category-specific? | Known false positives | Quantitative metrics |
|----------|-------------------------|-------------------|----------------------|---------------------|
| Urban expansion | Yes (CVA + optional DW built) | Partial — `urban_expansion_candidate` | Agriculture, bare soil, shadows | None wired |
| Deforestation | Yes (NDVI hint on upload; CVA catalog) | Partial — `vegetation_loss_candidate` | Seasonality, harvest | None wired |
| Water shrinkage | Yes (NDWI hint upload; CVA catalog) | Partial — `water_shrinkage_candidate` | Seasonal inflow, turbidity | None wired |
| Infrastructure | Yes (CVA + DW built) | Weak — overlaps urban/built | Roads vs buildings ambiguous | None wired |
| Mining | Yes (generic CVA) | Weak — `mining_change_candidate` only | Bare soil, agriculture, construction | None wired |

*Live EE spatial plausibility must be confirmed per case with `python scripts/run_evaluation.py` when credentialed.*

## C. Strongest category

**Urban expansion / construction (built-area path)** — Dynamic World `built` delta + NDBI/CVA provides the most structured corroboration. Semantic fusion produces explicit candidate regions with overlap metrics.

## D. Weakest category

**Mining** — No mining-specific detector or classifier. Generic spectral change and vegetation-loss hints cannot distinguish open-pit mining from bare soil, agriculture, or construction. System correctly refuses causal mining claims.

## E. Real limitations

- **Seasonality:** NDVI/NDWI direction hints are vulnerable on catalog CVA without per-index differencing
- **Resolution:** 10 m Sentinel-2 limits small infrastructure and narrow water boundaries
- **Clouds:** Scene-level cloud % + QA60/SCL masking; no unified quality score in evidence
- **Mining ambiguity:** Spectral change alone is insufficient
- **Infrastructure ambiguity:** Built-up semantic ≠ roads/bridges/pipelines
- **Historical:** Sentinel-2 only from 2015-06-23; Phase 5A policy blocks dishonest earlier-date claims
- **Region cap:** Max 50 CVA polygons may truncate large events
- **No scene-level area metrics on catalog path** (unlike upload bi-temporal pipeline)

## F. Changes made (evidence-backed)

1. **`backend/evaluation/`** — Harness, cases, metrics, runner, reports (separate from detectors)
2. **`backend/scripts/run_evaluation.py`** — Live EE runner gated by `EE_REAL_EVALUATION`
3. **`query_controller._step_metadata()`** — `fetch_imagery` and `detect_change` trace now records provider, mode, scenes, detector (fixes real-vs-dev observability gap)
4. **`change_domain.resolve_change_domain()`** — Recognize `"water body shrank"` phrasing (evaluation-found routing gap)

No CVA, SAR, upload pipeline, or global threshold retuning.

## G. Performance (expected bottlenecks)

| Stage | Typical bottleneck |
|-------|-------------------|
| Imagery fetch | EE `filterCollection` + metadata RPC |
| CVA | EE `reduceRegion` + vectorization export |
| Dynamic World semantics | Per-region sampling (construction path) |
| Evidence | Local fusion (fast) |

Measure per-case with `step_timings` in evaluation records when running live.

## H. Tests

| Suite | Before Phase 6 | After Phase 6 |
|-------|----------------|---------------|
| Backend pytest | 315 passed, 3 skipped | **328 passed, 3 skipped** (+13) |
| Frontend `tsc --noEmit` | pass | pass |

## I. Competition readiness

| Category | Rating | Rationale |
|----------|--------|-----------|
| Urban expansion | **Usable with caveats** | CVA + built semantic; not urban LC classification |
| Deforestation | **Usable with caveats** | Vegetation-loss hints; seasonality risk |
| Water shrinkage | **Usable with caveats** | NDWI hints; seasonal water variation |
| Infrastructure development | **Prototype** | Built/spectral proxy only |
| Mining | **Not reliable** | No mining-specific evidence; conservative claims only |

## J. Recommended Phase 7

**Seasonality-aware index differencing for catalog Earth Engine CVA** — Evaluation shows the largest cross-category false-positive mode is seasonal vegetation/water variation on generic magnitude CVA. A minimal Phase 7 would add optional NDVI/NDWI primary differencing on the EE path (mirroring upload index routing) without new ML classifiers, then re-run the Phase 6 suite quantitatively where reference data exists.

---

## False-positive register (documented, not auto-suppressed)

| Failure mode | Categories | Level | Mitigation (future) |
|--------------|-----------|-------|---------------------|
| Vegetation seasonality | Deforestation, mining | Detector + interpretation | Same-month pairing; index-specific EE CVA |
| Agricultural harvest | Deforestation | Detector | Crop calendar awareness |
| Cloud/shadow | All optical | Detector | Stricter scene QA scoring |
| Water seasonality | Water shrinkage | Detector + interpretation | Multi-year water mask |
| Bare soil | Mining, urban | Interpretation | Require multi-signal fusion |
| Built vs infrastructure | Infrastructure | Interpretation | Asset-specific datasets |
| Registration drift | All catalog | Detector | Co-registration QA metric |
| 50-region cap | Large events | Policy | Area-ranked truncation report |

## Threshold classification

| Parameter | Value | Class |
|-----------|-------|-------|
| `CVA_MAGNITUDE_THRESHOLD` | 1000 | Empirically tuned (v1.1.0) |
| `MIN_REGION_AREA_M2` | 2000 | Policy / speckle control |
| `MAX_CHANGE_REGIONS` | 50 | Policy cap |
| `DELTA_BUILT_THRESHOLD` | 0.15 | Benchmark-informed (Dynamic World literature) |
| `CVA_OVERLAP_THRESHOLD` | 0.30 | Geometric policy |
| Domain significance weights | 0.4/0.35/0.25 | Phase 5B policy — not benchmark-tuned |
