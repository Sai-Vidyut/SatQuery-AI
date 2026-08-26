# SIH Acceptance Test — Bi-Temporal Change Analysis

## Objective

Demonstrate the mandatory SIH multi-image capability: upload two spatially corresponding optical GeoTIFFs from different acquisition dates, ask a natural-language change question, and receive change description plus spatial evidence where CVA produces it.

## Preconditions

1. Backend running with upload storage configured (`UPLOAD_DIR`).
2. Phase 10 single-image VQA and Phase 11 scene description remain functional.
3. Local/CI uses `DeterministicChangeDetector` on uploaded pairs (development CVA — not Earth Engine catalog path).

## Temporal ordering policy

**Reject (do not auto-swap):** `earlier_image_id` must reference the image whose `acquisition_datetime` is strictly before `later_image_id`. Reversed ordering fails `input_validation` with a clear error.

## Test procedure

### Given

- Two georeferenced optical GeoTIFFs covering the same area
- Before image acquisition: `2023-01-01`
- After image acquisition: `2024-01-01`

### When

1. Open SatQuery workstation → **Temporal pair** mode.
2. Set before date `2023-01-01`, after date `2024-01-01`.
3. Upload earlier (before) GeoTIFF.
4. Upload later (after) GeoTIFF.
5. Enter query:
   > What changed between these two dates, and where did the change occur?
6. Click **Run Analysis**.

### Then

| Step | Expected |
|------|----------|
| Input validation | `input_validation` completed; pair overlap/temporal checks pass |
| Planner | `plan_query` intent = `bi_temporal_change_vqa` |
| CVA | `detect_change` completed via `deterministic_change_detector` |
| Understanding | `change_understanding` completed with query-specific summary |
| Evidence | `generate_evidence` completed; regions on map when CVA detects them |
| Answer | Non-empty change summary in inspector |
| Trace | Full tool chain visible |

## API equivalent

```bash
# Upload earlier + later with acquisition_datetime
curl -F "file=@before.tif" -F "modality=optical" -F "acquisition_datetime=2023-01-01T00:00:00+00:00" \
  http://localhost:8000/api/v1/imagery/upload
curl -F "file=@after.tif" -F "modality=optical" -F "acquisition_datetime=2024-01-01T00:00:00+00:00" \
  http://localhost:8000/api/v1/imagery/upload

curl -X POST http://localhost:8000/api/v1/query/submit \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What changed between these two dates, and where did the change occur?",
    "earlier_image_id": "<EARLIER_ID>",
    "later_image_id": "<LATER_ID>"
  }'
```

## Not in scope

- Cross-modal optical + SAR pair analysis
- GeoChat / RS-VLM fine-tuning
- Grounding
- Reference-mask benchmark evaluation

## Automated coverage

- Backend: `backend/tests/test_phase12_bi_temporal_change.py`
- Frontend E2E: `frontend/e2e/bi-temporal-change.spec.ts`
