# Phase 10 Report — Hackathon Demo Readiness

**Status:** Complete  
**Branch:** `feat/stronger-change-detection`  
**Non-goals honored:** No CVA/composite math changes, no upload/SAR/detector algorithm changes.

---

## 1. Imagery fallback policy

**Module:** `backend/app/adapters/imagery/earth_engine/composite.py`  
**Policy version:** `FALLBACK_POLICY_VERSION = 1.0.0` · composite `selection_policy = 2.1.0`

| Tier | Window | Decision |
|------|--------|----------|
| 1 | Requested anchor ±15d (seasonal) | `tier_1_seasonal_window` |
| 2 | Requested anchor ±60d (max) | `tier_2_widened_window` |
| 3 | Nearest valid scene | `tier_3_nearest_scene` |

- User-requested T1/T2 anchor dates are **never modified** on `ImageryScene.acquisition_date`.
- Fallback provenance per epoch: requested date, original window, fallback window, tier, reason, policy decision.
- `build_composite_epochs()` exposes `fallback_events[]` in composite provenance.
- If all tiers fail → `no_imagery_found` (404) with explicit message.

**Phase 9A impact:** Urban Bengaluru P8 failure (empty ±15d T1 window) should now resolve via tier 2/3 when scenes exist outside the strict window.

---

## 2. Water direction ambiguity

**Module:** `backend/app/services/change_domain.py`

- `is_water_direction_ambiguous()` — true when query domain is water shrinkage and direction hint contradicts (`water_expansion`), is missing, or claim strength is `DETECTED`.
- Answer wording: *"Water-related spectral change detected; the direction is inconclusive."*
- Does **not** claim "water shrank" or "water expanded" under ambiguity.
- Underlying `change_direction_hint` remains in detector metadata and trace.

---

## 3. Answer / evidence consistency

- `fuse_evidence` now passes `detector_metadata` and `confidence_kind` into fusion metadata (fixes domain answers missing detector context).
- `compose_domain_answer_clause()` accepts `region_count` / `candidate_count` — answers reference mapped regions when they exist.
- `_compose_domain_catalog_answer()` aligns region counts, area from detector metadata, and separability wording.
- No fabricated metrics; area only when present in detector metadata.

---

## 4. Frontend provenance additions

**Minimal inspector/trace extensions (no redesign):**

| Surface | Fields shown |
|---------|----------------|
| `ExecutionTrace` | T1/T2 requested + windows, scene counts, imagery strategy, fallback events, timing breakdown |
| `EvidenceInspector` | Data provenance panel: requested dates, strategy, detector, primary signal, direction hint, domain, changed area, confidence type, fallback note |
| `ConfidenceMeter` | Labelled **Detector separability** with histogram disclaimer |

---

## 5. Demo mode behavior

- `QueryRequest.demo_mode` + catalog UI checkbox **Demo mode**.
- Forces `DevelopmentImageryProvider` + deterministic detector path regardless of `IMAGERY_PROVIDER`.
- `AnalysisResult.demonstration_data` flag; answer text includes `[DEMONSTRATION DATA — not real Earth observation]`.
- Inspector banner: **DEMONSTRATION DATA — deterministic fixtures, not real Earth observation.**
- Production Earth Engine path unchanged when `demo_mode=false`.

---

## 6. Recommended live demo cases

Stored in `backend/evaluation/cases/live_demo_cases.json` (from Phase 9A qualitative runs):

| Case | Why |
|------|-----|
| **Deforestation — Amazon Rondônia** | Stable dry-season scenes, clear vegetation loss, ~9 regions, moderate runtime |
| **Infrastructure — Dubai south** | Reliable coverage, obvious built growth, completed in 9A |
| **Mining — Saxony** | Consistent completion, many regions, good European S2 revisit |

**Avoid for live demo (9A):** Urban Bengaluru (scene gaps / fallback-sensitive), Lake Mead water (direction instability).

---

## 7. Evaluation harness improvements

`EvaluationRecord` now captures:

- `requested_earlier_date` / `requested_later_date`
- `actual_t1_window` / `actual_t2_window`
- `fallback_events`, `confidence_semantics`, `demonstration_data`
- Step timings + total duration (unchanged, now documented in runner)

Ground-truth readiness: `evaluation/GROUND_TRUTH_READINESS.md` + `evaluation/fixtures/ground_truth_example.json`.

---

## 8. Stale state / error handling

- **Stale state:** `Workspace` clears `result`, `selectedRegionId`, and `analysisError` on each submit; map receives `evidence={result?.evidence ?? []}`.
- **Error UX:** `user_facing_message()` map in `app/core/user_errors.py`; API returns `user_message` alongside `code`.
- **Trace:** Failed steps record `error_code` in metadata.
- **Frontend:** `ApiError` + `normalizeAnalysisError()` map codes to operator messages.

---

## 9. Performance observability

`ExecutionTrace` shows timing breakdown for fetch_imagery, detect_change, analyze_semantics, generate_evidence, and total — from existing `duration_ms` on trace steps. No optimization performed.

---

## 10. Tests

| Metric | Before Phase 10 | After Phase 10 |
|--------|-----------------|----------------|
| Backend pytest | 368 passed, 3 skipped | **381 passed**, 3 skipped |
| Frontend `tsc` | pass | **pass** |
| New tests | — | `tests/test_phase10_demo_readiness.py` (13 cases) |

Coverage: fallback tiers, fallback provenance, water ambiguity wording, fuse metadata, answer consistency, demo labelling, error messages, `demo_mode` schema.

---

## 11. Remaining limitations

- Water direction still depends on index differencing — ambiguity handling is answer-layer only.
- Tier-3 nearest-scene fallback may increase seasonality risk (warned in provenance).
- Demo mode uses seeded deterministic polygons — not domain-calibrated fixtures per AOI.
- No quantitative benchmark pipeline or GT download.
- Urban / water live demos remain higher risk than deforestation / infrastructure / mining.

---

## 12. Recommended Phase 11

1. **Curated demo fixtures** — per-domain deterministic regions aligned with query semantics (not generic seeded polygons).
2. **Water direction policy** — detector-level consensus rule (NDWI + area trend) before claiming shrinkage/expansion.
3. **Frontend session hardening** — explicit trace reset + loading skeleton on map during run.
4. **Ground-truth pilot** — wire EuroMineNet or PRODES subset into one quantitative evaluation case.
5. **Live demo playbook** — scripted AOI/date presets in UI linked to `live_demo_cases.json`.

**Stop here — Phase 11 not started.**
