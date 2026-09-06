# Phase 8 — Multi-Scene Seasonal Composites + Real EE Validation Report

Live Earth Engine execution requires credentials (`EE_REAL_EVALUATION=true`, `EARTH_ENGINE_PROJECT`, GCP auth). **No credentialed live run was executed in CI/dev** — before/after comparison is structural + unit-tested; re-run `python scripts/run_evaluation.py` when credentialed.

## 1. Provider architecture changes

| Component | Phase 7 (single anchor) | Phase 8 (composite) |
|-----------|-------------------------|---------------------|
| Scene selection | `select_anchor_scenes` → 1 scene per epoch | `build_composite_epochs` → N scenes per epoch |
| `ImageryScene.platform_id` | `COPERNICUS/S2_SR_HARMONIZED/...` | `COMPOSITE/MEDIAN/t1` or `t2` |
| `ImageryScene.acquisition_date` | Actual scene date | **User-requested anchor date** (unchanged) |
| Detector input | `ee.Image(platform_id)` | `build_median_composite_image(scene_platform_ids)` |
| Dynamic World | Anchor date ±0/+7d | **Composite window** `[anchor±15d]` |

**New modules:**
- `adapters/imagery/earth_engine/composite.py` — policy, windowing, scene selection, provenance
- `adapters/change/earth_engine/composite_loader.py` — median composite build + coverage validation
- `adapters/semantic/earth_engine/imagery_epoch.py` — DW window alignment

**Unchanged:** upload pipeline, deterministic detector, SAR, building policy, CVA math, index thresholds.

## 2. Composite policy (v2.0.0)

| Parameter | Value |
|-----------|-------|
| Window | ±15 days around requested anchor |
| Method | Cloud-masked per-scene median (`QA60` + `SCL` before compositing) |
| Scene cap | 12 per epoch |
| Minimum scenes | 1 (warning if < 2) |
| Seasonal preference | Same sort key as Phase 7 within window |
| User dates | Never silently replaced |

## 3. Scene-selection behavior

1. Query all candidates in `[earlier_date, later_date]` with scene-level cloud filter.
2. T1: filter candidates to `[requested_start − 15d, requested_start + 15d]`.
3. T2: filter candidates to `[requested_end − 15d, requested_end + 15d]`.
4. Rank by seasonal preference → date distance → cloud → scene_id.
5. Return top N scenes per epoch; build composite metadata.

**Errors:** `no_imagery_found` if zero scenes in either window; `invalid_date_range` if windows overlap invalidly; `insufficient_imagery` if composite has zero valid AOI pixels after masking.

## 4. Composite method

```python
masked_scenes = [mask_sentinel2_sr(ee.Image(pid)).select(CVA_BANDS) for pid in platform_ids]
composite = ee.ImageCollection.fromImages(masked_scenes).median()
```

Single-scene epochs skip median (use that scene directly). Domain index differencing (NDVI/NDWI/NDBI) runs on the same masked composite bands.

## 5. Dynamic World alignment

`imagery_epoch_window()` returns composite `[window_start, window_end]` for composite epochs instead of single-anchor ±7d. Preserves existing DW collection and date policy; does not claim pre-DW history.

## 6. Provenance changes

`provider_metadata` and trace `fetch_imagery` step now include:

```json
{
  "imagery_strategy": "seasonal_median_composite",
  "composite_method": "median",
  "seasonality_policy": "1.0.0",
  "selection_policy": "2.0.0",
  "t1": {
    "requested_date": "2018-06-01",
    "window_start": "2018-05-17",
    "window_end": "2018-06-16",
    "scene_count": 3,
    "scene_dates": ["2018-05-20", "2018-06-03", "2018-06-12"]
  },
  "t2": { "...": "..." }
}
```

Frontend `ExecutionTrace` shows composite windows and scene counts (no single-scene date claim).

## 7. Before / after live EE evaluation

| Status | Detail |
|--------|--------|
| Live EE run | **Not executed** — `EE_REAL_EVALUATION` / GCP credentials unavailable |
| Harness | Updated `evaluation/runner.py` + `scripts/run_evaluation.py` for composite provenance |
| Expected Phase 7 → 8 delta | Fewer cloud-gap false positives; higher EE latency; more scenes per epoch |

**To run when credentialed:**
```bash
export IMAGERY_PROVIDER=earth_engine
export CHANGE_DETECTOR=earth_engine
export EE_REAL_EVALUATION=true
cd backend && python scripts/run_evaluation.py --output evaluation/reports/phase8_live.json --markdown evaluation/reports/phase8_live.md
```

No quantitative improvement percentages claimed without live results.

## 8. Seasonality false-positive behavior (expected)

| Scenario | Expected composite effect |
|----------|---------------------------|
| Vegetation phenology, no loss | Median reduces single-scene noise; NDVI path unchanged |
| Crop cycles | Partial smoothing within 30-day window; not eliminated |
| Water seasonality | NDWI on median may stabilize shoreline; inflow variation remains |
| Cloud/mask artifacts | Median should reduce single-scene cloud-edge FP |
| Genuine persistent change | Should remain detectable if consistent across epoch |

**Honest assessment:** Compositing helps cloud/mask fragility more than cross-season phenology. Phase 7 cross-season warnings remain.

## 9. Performance (expected)

| Stage | Phase 7 | Phase 8 (expected) |
|-------|---------|-------------------|
| Scenes per epoch | 1 | 1–12 |
| EE median compositing | None | O(N) loads per epoch |
| Coverage validation | None | 2× `reduceRegion` per detection |
| Total query time | Lower | Higher (not measured live) |

Do not optimize before credentialed measurement.

## 10. Tests before / after

| Suite | Phase 7 | Phase 8 |
|-------|---------|---------|
| Backend pytest | 353 passed | **368 passed** (+15) |
| Frontend `tsc` | pass | pass |
| New | — | `test_phase8_composite.py` |

## 11. Five-category readiness (unchanged pending live validation)

| Category | Rating | Notes |
|----------|--------|-------|
| Urban expansion | Usable with caveats | NDBI + DW built; composite reduces cloud FP (unverified live) |
| Deforestation | Usable with caveats | NDVI composite; phenology risk remains |
| Water shrinkage | Usable with caveats | NDWI composite; seasonal inflow risk remains |
| Infrastructure | Prototype | Built proxy only |
| Mining | Not reliable | No mining-specific detector |

**Do not upgrade ratings without live EE evidence.**

## 12. Remaining scientific limitations

- 30-day window may miss optimal phenological match across years
- Median does not remove cross-season comparison bias
- Policy index thresholds unchanged (not benchmark-tuned)
- No Landsat historical extension
- 50-region cap unchanged
- Mining still not reliable

## 13. Recommendation for Phase 9

**If live evaluation shows material improvement:** stop detection-method work; move to product/evidence/demo hardening (auth, reports, map UX, quantitative GT wiring for EuroMineNet/PRODES subsets).

**If live evaluation shows no material improvement:** do not add algorithmic complexity; document limitations honestly and focus on demo hardening + optional SAR/multimodal fusion for specific domains.

**Do not start Phase 9 without credentialed Phase 8 live run results.**

---

## Threshold classification (unchanged)

All CVA, index, min-area, and max-region thresholds from Phase 7 remain unchanged.
