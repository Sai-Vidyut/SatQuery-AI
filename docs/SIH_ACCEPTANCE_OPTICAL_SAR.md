# SIH Acceptance — Cross-Modal Optical + SAR Analysis (Phase 13)

## Scope

Mandatory SIH capability: joint analysis of a co-located optical/multispectral image and SAR image of the same geographic area, with explicit fusion (not answer concatenation).

## Preconditions

1. Backend running with `UPLOAD_DIR` writable.
2. Trusted benchmark pair **or** two overlapping GeoTIFF uploads:
   - Slot 1: optical/multispectral (`modality=optical`)
   - Slot 2: SAR (`modality=sar`)
3. For verified co-registration demo: upload both images with `benchmark_dataset=true`, `co_registered_benchmark_pair=true`, and matching `benchmark_pair_id` (server-audited; arbitrary client claims are ignored without `benchmark_dataset`).

## Acceptance procedure

1. Open the workstation and select **Cross-modal** composer mode.
2. Upload the optical/multispectral GeoTIFF to the **Optical** slot.
3. Upload the SAR GeoTIFF to the **SAR** slot.
4. Confirm compatibility indicators (modality, overlap, co-registration status).
5. Enter the representative query:

   > Use the optical and SAR images together to identify built-up and water-covered regions.

6. Submit the analysis.

## Expected system behavior

| Step | Expected |
|------|----------|
| Input validation | Both images readable; optical+SAR modalities; spatial overlap checked; co-registration status declared honestly |
| Planner intent | `cross_modal_optical_sar` |
| Specialists | `optical_analysis`, `sar_analysis` |
| Fusion | `cross_modal_fusion` (explicit joint stage) |
| Evidence | Fused regions reference fusion policy; no fabricated aggregate confidence |
| Trace | `input_validation` → `plan_query` → `optical_analysis` → `sar_analysis` → `cross_modal_fusion` → `generate_evidence` |
| GUI | Optical analysis, SAR analysis, joint analysis, evidence, and trace visible |

## Co-registration honesty

- **Without** matching benchmark pair tokens: status must be `overlap_only_not_verified` (or `unknown` if bounds missing).
- **With** audited benchmark pair upload on both images: status may be `verified_benchmark` with provenance citing the pair token.

The system must **not** claim verified co-registration from overlap alone.

## Development vs production

- Uploaded cross-modal path uses **development** specialists (`development_uploaded_optical_analysis`, `development_uploaded_sar_analysis`, `uploaded_cross_modal_fusion_v1.0.0`).
- Earth Engine catalog CVA/SAR/fusion is **not** applied to arbitrary uploads.
- Real optical/SAR inference on uploads requires future provider wiring.

## Automated coverage

See `backend/tests/test_phase13_cross_modal_optical_sar.py` and `frontend/e2e/cross-modal.spec.ts`.
