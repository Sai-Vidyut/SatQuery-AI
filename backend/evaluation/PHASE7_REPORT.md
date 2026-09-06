# Phase 7 — Seasonality-Aware Catalog Change Detection Report

Live Earth Engine execution requires credentials (`EE_REAL_EVALUATION=true`). Quantitative before/after comparison requires a credentialed re-run of `python scripts/run_evaluation.py`.

## 1. Root cause of seasonal false positives

The catalog Earth Engine path compared two single Sentinel-2 anchor scenes using **generic 6-band Euclidean CVA** regardless of query domain. Phenological shifts (vegetation green-up/senescence, seasonal water extent, crop cycles) produce large multispectral magnitude even when no persistent land-cover change occurred.

Contributing factors:

| Factor | Effect |
|--------|--------|
| Closest-date anchor selection (v1.0.0) | Could pick phenologically mismatched scenes when several candidates were similarly close in days |
| No cross-season warning | January vs September comparisons proceeded without surfacing seasonality risk |
| CVA on raw SR bands | Sensitive to vegetation/water spectral shifts that NDVI/NDWI would partially normalize |
| Domain context not reaching detector | `change_domain` / `query_hint` affected post-hoc annotation only, not detection |
| Requested vs actual dates undocumented in CVA output | Users could not see anchor drift |

Phase 6 evaluation identified seasonality as the dominant cross-category false-positive mode.

## 2. Chosen mitigation

**Two-part policy (minimal complexity, EE-architecture fit):**

### A. Seasonal scene-selection preference (imagery v1.1.0)

`select_anchor_scenes` now sorts candidates by `(seasonal_penalty, day_distance, cloud, scene_id)` where `seasonal_penalty` prefers scenes within ±1 calendar month of the requested anchor date.

- User-requested dates are **not altered**
- Selected scene dates and offsets are recorded in `provider_metadata.seasonality`
- Cross-season T1/T2 pairs (month gap > 3) emit a **warning**, not rejection

### B. Domain-aware index differencing (detector v1.2.0)

When `change_domain` or domain-resolvable `query_hint` is present:

| Domain | Primary index |
|--------|---------------|
| Deforestation | NDVI |
| Water shrinkage | NDWI |
| Urban expansion | NDBI |
| Infrastructure | NDBI |
| Mining | NDVI |

Detection uses **absolute index difference** with policy thresholds (NDVI 0.15, NDWI 0.12, NDBI 0.12). Generic `spectral_change` without domain continues to use **unchanged CVA**.

**Recommendation implemented:** domain-specific indices are the **primary detection signal** for domain-aware catalog queries — not a post-hoc filter or normalization layer on CVA.

## 3. Alternatives considered

| Approach | Verdict |
|----------|---------|
| Percentile normalization within AOI | Rejected — adds EE reduceRegion cost; hard to interpret per-domain |
| Temporal compositing / median composites | Deferred — requires provider refactor to return composites; not clean fit |
| Seasonal baseline adjustment (multi-year) | Rejected — needs historical archive policy beyond current anchor model |
| Same-season strict rejection | Rejected — would block valid user queries; warning preferred |
| ML phenology classifier | Out of scope per requirements |
| Global CVA replacement | Rejected — generic path unchanged |

## 4. Earth Engine path changes

| File | Change |
|------|--------|
| `adapters/imagery/earth_engine/seasonality.py` | New — seasonality policy, provenance builder, cross-season detection |
| `adapters/imagery/earth_engine/selection.py` | v1.1.0 seasonal preference in sort key |
| `adapters/imagery/earth_engine/constants.py` | `SELECTION_POLICY_VERSION = 1.1.0` |
| `adapters/imagery/earth_engine/provider.py` | Attach `seasonality` provenance to S2 `provider_metadata` |
| `adapters/change/earth_engine/indices.py` | New — EE NDVI/NDWI/NDBI + domain routing |
| `adapters/change/earth_engine/constants.py` | `DETECTOR_VERSION = 1.2.0`, index thresholds |
| `adapters/change/earth_engine/detector.py` | Route domain queries to index differencing; provenance |
| `schemas/domain.py` | `ChangeDetectionInput.change_domain` field |
| `services/query_controller.py` | Pass `query_hint`, `change_domain`; trace seasonality |

**Not modified:** upload bi-temporal pipeline, deterministic detector, SAR detector, building-instance policy, frontend.

## 5. Provenance changes

Compact `provider_metadata.seasonality` records requested vs actual dates, offsets, cross-season flag, and warnings. `detector_metadata` adds `primary_index`, `method`, `change_direction_hint`, acquisition dates, and `seasonality_warnings`.

## 6. Evaluation before vs after

Phase 6 catalog cases already use same-month pairing. Phase 7 improvements are expected on deforestation/water (index path) and cross-season queries (warning). No quantitative GT — live EE re-run required. Synthetic fixtures: `evaluation/cases/seasonality_cases.json`.

## 7. False-positive behavior

| Scenario | Phase 7 behavior |
|----------|------------------|
| Vegetation seasonality, no loss | NDVI + sub-threshold median → `no_change` |
| Water seasonality, no shrinkage | NDWI + sub-threshold → `no_change` |
| Genuine vegetation loss | NDVI decrease → `vegetation_loss` |
| Genuine water shrinkage | NDWI decrease → `water_contraction` |
| Cross-season Jan vs Sep | Warning in provenance |

## 8. Performance impact

Domain path adds one EE `reduceRegion` (median) for direction hint. No compositing cost added.

## 9. Tests before vs after

| Suite | Before Phase 7 | After Phase 7 |
|-------|----------------|---------------|
| Backend pytest | 328 passed, 3 skipped | **353 passed, 3 skipped** (+25) |
| Frontend `tsc --noEmit` | pass | pass |

## 10. Five-category readiness after Phase 7

| Category | Rating |
|----------|--------|
| Urban expansion | Usable with caveats (NDBI primary) |
| Deforestation | Usable with caveats (NDVI primary) |
| Water shrinkage | Usable with caveats (NDWI primary) |
| Infrastructure | Prototype |
| Mining | Not reliable |

## 11. Remaining weaknesses

No compositing, policy-only index thresholds, cross-season warning does not block, no BRDF normalization, mining still generic.

## 12. Recommended Phase 8

Multi-scene seasonal median compositing per anchor with composite provenance; benchmark-tuned index thresholds where reference data exists.

## Threshold classification

| Parameter | Value | Phase 7 change |
|-----------|-------|----------------|
| `CVA_MAGNITUDE_THRESHOLD` | 1000 | **Unchanged** |
| `MIN_REGION_AREA_M2` | 2000 | **Unchanged** |
| `MAX_CHANGE_REGIONS` | 50 | **Unchanged** |
| `INDEX_CHANGE_THRESHOLD_NDVI` | 0.15 | New — domain path only |
| `INDEX_CHANGE_THRESHOLD_NDWI` | 0.12 | New — domain path only |
| `INDEX_CHANGE_THRESHOLD_NDBI` | 0.12 | New — domain path only |
