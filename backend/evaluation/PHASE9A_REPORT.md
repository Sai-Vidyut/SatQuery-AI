# Phase 9A — Credentialed Real Earth Engine Validation Report

**Date:** 2026-09-06  
**EE project:** `satquery-ai` (from existing `.env` + `earthengine authenticate`)  
**Harness:** `scripts/run_evaluation.py` with `EE_REAL_EVALUATION=true`  
**Artifacts:** `evaluation/reports/phase9a_phase7.json`, `phase9a_phase8.json` (+ markdown summaries)

Phase 7 run: git worktree at commit `6be62cb` (single-anchor + seasonal selection).  
Phase 8 run: current working tree (seasonal median composite v2.0.0).

No credentials or key files committed.

---

## 1. Live cases successfully executed

| Case | Phase 7 | Phase 8 |
|------|---------|---------|
| `urban_expansion_bengaluru_east` | **Completed** (0 regions) | **Failed** (`no_imagery_found` — zero scenes in T1 composite window) |
| `deforestation_amazon_rondonia` | Completed | Completed |
| `water_shrinkage_lake_mead` | Completed | Completed |
| `infrastructure_dubai_south` | Completed | Completed |
| `mining_disturbance_eu_reference` | Completed | Completed |

**4/5 catalog cases completed in both runs.**  
**Seasonality negative cases** (`evaluation/cases/seasonality_cases.json`) were **not executed live** — fixtures lack AOI/query required by the harness. Qualitative seasonality assessment is inferred only from overlapping catalog behavior (see §5).

---

## 2. Phase 7 vs Phase 8 results (measured)

| Case | P7 regions | P8 regions | Δ regions | P7 area (m²) | P8 area (m²) | P7 direction hint | P8 direction hint | P7 total (ms) | P8 total (ms) |
|------|-----------|-----------|-----------|-------------|-------------|-------------------|-------------------|--------------|--------------|
| Urban Bengaluru | 0 | — (failed) | — | — | — | `no_change` | — | 560,785 | 541,343 (fail) |
| Deforestation Amazon | 13 | 9 | **−4** | 1,235,497 | 906,904 | `vegetation_loss` | `vegetation_loss` | 110,979 | 128,222 |
| Water Lake Mead | 3 | 6 | **+3** | 965,643 | 897,134 | `water_contraction` | **`water_expansion`** | 974,219 | 982,530 |
| Infrastructure Dubai | 6 | 8 | +2 | 1,880,475 | 1,765,975 | `built_up_decrease` | `built_up_decrease` | 431,142 | 427,288 |
| Mining Saxony | 24 | 23 | −1 | 5,118,023 | 5,172,597 | `vegetation_gain` | `vegetation_gain` | 488,529 | 499,367 |

All cases: `evaluation_type = qualitative` (no polygon ground truth).

### Imagery epochs

**Phase 7 (single anchor — actual scene dates used for detection):**

| Case | T1 scene date | T2 scene date |
|------|---------------|---------------|
| Urban | 2019-05-14 | 2024-05-07 |
| Deforestation | 2019-08-01 | 2023-07-31 |
| Water | 2016-06-05 | 2022-05-30 |
| Infrastructure | 2018-01-09 | 2023-12-19 |
| Mining | 2017-06-06 | 2023-05-31 |

Note: Urban P7 did **not** use 2018-06 / 2024-06 anchors — closest scenes in catalog range were May 2019 / May 2024.

**Phase 8 (composite windows — requested anchors preserved in metadata):**

| Case | T1 window | T1 scenes | T2 window | T2 scenes |
|------|-----------|-----------|-----------|-----------|
| Urban | — | — | — | — (failed) |
| Deforestation | 2019-07-17–08-16 | 4 | 2023-07-17–08-16 | 3 |
| Water | 2016-05-17–06-16 | 4 | 2022-05-17–06-16 | 6 |
| Infrastructure | 2017-12-17–2018-01-16 | 2 | 2023-12-17–2024-01-16 | 1 |
| Mining | 2017-05-17–06-16 | 1 | 2023-05-17–06-16 | 4 |

---

## 3. Strongest improvements (Phase 8)

| Observation | Case | Evidence |
|-------------|------|----------|
| Fewer change polygons | Deforestation | 13 → 9 regions (−31%); area −27% — consistent with suppressing single-scene speckle/noise |
| Honest anchor metadata | All P8 completes | Trace reports composite windows + scene counts; requested dates not conflated with a single granule |
| Similar total runtime | 4 comparable cases | Median Δ total time +2% (not a material regression) |

No case showed a clear qualitative improvement in **answer quality** or **domain claim strength** — all completed cases still report “no strong [domain] signal alignment” despite candidate regions.

---

## 4. Regressions (Phase 8)

| Issue | Case | Evidence |
|-------|------|----------|
| **Hard failure** | Urban Bengaluru | `no_imagery_found` — zero scenes in T1 ±15d window around 2018-06-01; P7 succeeded by picking 2019-05-14 |
| **Wrong direction hint** | Water Lake Mead | P7 `water_contraction` → P8 `water_expansion` (domain interpretation worsened) |
| **More false-positive polygons** | Water Lake Mead | 3 → 6 regions despite similar total area |
| **Low-scene composites** | Infrastructure T2, Mining T1 | Only 1 scene in epoch — composite provides no multi-scene benefit |

---

## 5. False positives & seasonality (qualitative)

| Scientific question | Finding |
|---------------------|---------|
| Cloud/mask artifacts | Deforestation region count dropped with composites — weak evidence of speckle reduction |
| Transient scene noise | Mixed — water regions **increased** |
| Seasonal false positives | **Not improved** — Lake Mead direction hint flipped to expansion on multi-scene median |
| Water-boundary stability | **Worse** — more regions, wrong NDWI direction |
| Vegetation stability | Deforestation region count down; direction unchanged (`vegetation_loss`) |
| Genuine change blurred | Cannot confirm without GT; deforestation area −27% may indicate lost sensitivity |
| Small regions | Region cap (50) not hit; small-change sensitivity not clearly improved |
| Runtime | Fetch dominates (~80–99% of total); compositing adds modest fetch overhead |
| Domain interpretation | Water case domain support **degraded** (contraction → expansion) |

**Seasonality fixtures not run live** (no AOI). Overlap with catalog cases:
- `tp_genuine_water_shrinkage` ≈ Lake Mead (P8 regressed on direction)
- `tp_genuine_vegetation_loss` ≈ Amazon (P8 fewer regions, same hint)
- `fp_water_seasonality` / `fp_vegetation_seasonality` — **not directly testable** without new AOIs

---

## 6. Performance (measured)

| Case | P7 fetch (ms) | P8 fetch (ms) | P7 detect (ms) | P8 detect (ms) | P7 total (ms) | P8 total (ms) |
|------|--------------|--------------|---------------|---------------|--------------|--------------|
| Deforestation | 104,900 | 119,291 | 5,974 | 8,825 | 110,979 | 128,222 |
| Water | 968,135 | 969,513 | 5,980 | 12,908 | 974,219 | 982,530 |
| Infrastructure | 404,534 | 389,101 | 12,513 | 15,088 | 431,142 | 427,288 |
| Mining | 478,604 | 486,165 | 9,820 | 13,094 | 488,529 | 499,367 |

- **Scene count:** P7 always 2 granules; P8 uses 1–6 per epoch (median of N).
- **Bottleneck:** Earth Engine `fetch_imagery` (scene query + composite build), not local fusion/evidence.
- **Compositing latency:** +0–14% total time on completed cases — acceptable but not free.

---

## 7. Five-category readiness (live-evidence based)

| Category | Rating | Live evidence |
|----------|--------|---------------|
| **Urban expansion** | **Usable with caveats** | Bengaluru: P7 zero change (anchor drift to 2019/2024); P8 fails on sparse 2018 window |
| **Deforestation** | **Usable with caveats** | Change detected; composites slightly reduce region count; no GT |
| **Water shrinkage** | **Usable with caveats** | P8 **worse** direction hint vs P7 on Lake Mead; not upgraded |
| **Infrastructure** | **Prototype** | Built/NDBI proxy; direction `built_up_decrease` inconsistent with growth query |
| **Mining** | **Not reliable** | 23–24 generic regions; `vegetation_gain` hint wrong for open-pit disturbance |

Ratings unchanged or **downgraded in confidence** for water (P8 regression). No category promoted to “Ready.”

---

## 8. Should composite detection work STOP?

**Yes — recommend stopping further catalog detection-method work.**

Live EE validation does **not** show material improvement:
- 1/5 cases fails outright (urban)
- 1/4 completed cases regresses domain direction (water)
- 1/4 shows modest noise reduction (deforestation) without better answers
- 2/4 are effectively unchanged (infrastructure, mining)

Phase 7 single-anchor + index differencing already captures most value. Phase 8 composites add complexity, sparse-window failures, and inconsistent domain hints without improving answer quality.

---

## 9. Recommended Phase 10 (not started)

**Product / demo / evidence hardening** — not algorithm work:

1. **Operational fallback:** when composite window has zero scenes, fall back to single-anchor selection (policy-only; defer unless product requires)
2. **Provenance UX:** ship Phase 8 trace composite display (already implemented in frontend trace)
3. **Evaluation expansion:** add AOI to seasonality fixtures for live negative-case testing
4. **Quantitative GT:** wire EuroMineNet / PRODES subsets where licenses permit
5. **Demo reliability:** document anchor-date vs scene-date behavior for competition judges
6. **Auth / reports / map polish** per competition needs

Do **not** pursue: multi-year baselines, ML classifiers, Landsat extension, or further compositing variants without new GT showing benefit.

---

## 10. Frontend provenance check

Trace `fetch_imagery` summaries are factually correct:
- Phase 7: `"Acquired 2 scene(s) via google-earth-engine"`
- Phase 8: `"Built median composites: T1 N scenes (window), T2 M scenes (window)"`

Phase 8 `ExecutionTrace` UI (uncommitted) shows composite windows and scene counts when `imagery_strategy=seasonal_median_composite`. **No misleading single-image claim when composites are used.** Minimal fix not required for factual accuracy; shipping the existing trace detail is recommended in Phase 10.

---

## Threshold discipline

No thresholds were changed during Phase 9A. All results use Phase 7/8 policy values unchanged.
