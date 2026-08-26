# SIH Acceptance Test — Single-Image VQA

## Objective

Demonstrate the mandatory SIH capability: upload one optical GeoTIFF, ask a natural-language question, and receive a genuine remote-sensing VQA answer with full execution trace and model provenance.

## Preconditions

1. Backend running with upload storage configured (`UPLOAD_DIR`).
2. For **production demonstration** (real GeoChat-7B):
   - GPU inference service reachable at `GEOCHAT_SERVICE_URL`
   - `GEOCHAT_VQA_PROVIDER=geochat_service`
   - Service hosts Phase 9B reference config (8-bit GeoChat-7B on T4-class GPU)
3. For **local/CI development**:
   - `GEOCHAT_VQA_PROVIDER=development` (labeled mock — not SIH production demo)

## Test procedure

### Given

- A valid georeferenced Sentinel-2 optical GeoTIFF (e.g. `experiments/phase9b_geochat/assets/` scene or any Phase 8 test GeoTIFF)

### When

1. Open SatQuery workstation → **Upload image** mode.
2. Upload the GeoTIFF (validation must succeed).
3. Enter query:
   > Describe the land-cover and major objects visible in this image.
4. Click **Run Analysis**.

### Then

| Step | Expected |
|------|----------|
| Input validation | `input_validation` trace step **completed** |
| Planner | `plan_query` intent = `single_image_vqa`, tools include `geochat_vqa` |
| Specialist | `geochat_vqa` trace step **completed** with provider + model metadata |
| Answer | Non-empty answer in inspector (genuine model output for `geochat_service`) |
| Provenance | Inspector shows `MBZUAI/geochat-7B` for production provider |
| Confidence | Shown as **unavailable** unless model exposes calibrated confidence |
| Evidence | No fabricated GeoJSON regions; spatial evidence list may be empty |

## API equivalent

```bash
# 1. Upload
curl -F "file=@scene.tif" -F "modality=optical" http://localhost:8000/api/v1/imagery/upload

# 2. Submit VQA (use image id from upload response)
curl -X POST http://localhost:8000/api/v1/query/submit \
  -H 'Content-Type: application/json' \
  -d '{"query":"Describe the land-cover and major objects visible in this image.","image_id":"<IMAGE_ID>"}'
```

## Regression

- Existing AOI + date catalog workflow (`POST /api/v1/query/submit` without `image_id`) must remain unchanged.

## Automated coverage

- Backend: `backend/tests/test_phase10_single_image_vqa.py` (SIH tests 1–8)
- Frontend E2E: `frontend/e2e/upload-vqa.spec.ts` (SIH test 10)
