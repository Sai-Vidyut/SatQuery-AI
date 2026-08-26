# SIH Acceptance Test — Single-Image Scene Description

## Objective

Demonstrate the second mandatory SIH single-image capability: upload one optical or SAR GeoTIFF, request a general scene description, and receive a structured caption from the remote-sensing VLM with full execution trace and model provenance.

## Preconditions

1. Backend running with upload storage configured (`UPLOAD_DIR`).
2. Phase 10 single-image VQA must remain functional.
3. For **production demonstration** (real GeoChat-7B):
   - GPU inference service reachable at `GEOCHAT_SERVICE_URL`
   - `GEOCHAT_VQA_PROVIDER=geochat_service`
   - Service exposes `POST /v1/caption` (scene-description mode, not disguised VQA)
4. For **local/CI development**:
   - `GEOCHAT_VQA_PROVIDER=development` (labeled mock — not SIH production demo)

## Test procedure

### Given

- A valid georeferenced optical GeoTIFF (production path) or SAR GeoTIFF

### When

1. Open SatQuery workstation → **Upload image** mode.
2. Upload the GeoTIFF (validation must succeed).
3. Enter query:
   > Describe this satellite scene.
4. Click **Run Analysis**.

### Then

| Step | Expected |
|------|----------|
| Input validation | `input_validation` trace step **completed** |
| Planner | `plan_query` intent = `single_image_caption`, tools include `geochat_caption` |
| Specialist | `geochat_caption` trace step **completed** with provider + model metadata |
| Description | Non-empty scene description in inspector |
| Provenance | Inspector shows model (`MBZUAI/geochat-7B` for production provider) and provider |
| Task label | UI distinguishes **Scene Description** from VQA |
| Confidence | Shown as **unavailable** unless model exposes calibrated confidence |
| Evidence | No fabricated GeoJSON regions, bounding boxes, or masks |

## API equivalent

```bash
# 1. Upload
curl -F "file=@scene.tif" -F "modality=optical" http://localhost:8000/api/v1/imagery/upload

# 2. Submit scene description (use image id from upload response)
curl -X POST http://localhost:8000/api/v1/query/submit \
  -H 'Content-Type: application/json' \
  -d '{"query":"Describe this satellite scene.","image_id":"<IMAGE_ID>"}'
```

## Regression

- Phase 10 VQA queries (e.g. `What land-cover types are visible?`) must route to `single_image_vqa` / `geochat_vqa`, not caption.
- Existing AOI + date catalog workflow must remain unchanged.

## Automated coverage

- Backend: `backend/tests/test_phase11_single_image_caption.py` (SIH tests 1–11)
- Frontend E2E: `frontend/e2e/scene-caption.spec.ts` (SIH test 12)
