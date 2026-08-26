# Phase 9B — GeoChat Colab Smoke Test

Isolated research artifact. **Not imported by `backend/` or `frontend/`.**

Runs genuine `MBZUAI/geochat-7B` VQA inference on a real Sentinel-2 L2A
image inside a **CUDA GPU runtime** (Google Colab T4).

## Quick start (Colab)

1. **Push the smoke image to GitHub** (one-time, if not already on `main`):
   ```bash
   git add experiments/phase9b_geochat/assets/sentinel2_smoketest.png
   git commit -m "add Phase 9B Colab smoke-test Sentinel-2 image"
   git push
   ```
2. Generate the notebook on your Mac:
   ```bash
   cd experiments/phase9b_geochat
   python3 generate_colab_artifacts.py
   ```
3. In Colab: **File → Upload notebook** → `colab_geochat_smoke_test.ipynb`
4. **Runtime → Change runtime type → T4 GPU**
5. **Runtime → Run all**

If cell 4 cannot download the PNG from GitHub (404), it will prompt you to
upload **only** `assets/sentinel2_smoketest.png` from this folder.

6. Download `/content/phase9b_geochat_smoke/smoke_test_result.json` on success.

## Notebook structure (8 small code cells)

| Cell | Purpose |
|------|---------|
| 1 | Python / CUDA / GPU / `nvidia-smi` |
| 2 | Install inference deps (`transformers==4.36.2`, etc.) |
| 3 | Clone `mbzuai-oryx/GeoChat` |
| 4 | Download Sentinel-2 PNG from GitHub raw URL (upload fallback) |
| 5 | Phase 9A MPT patch + Phase 9B CLIP defer-interpolation patch |
| 6 | Load GeoChat-7B on T4 (8-bit LLM; CLIP 504 interpolation after checkpoint) |
| 7 | One genuine VQA inference |
| 8 | Write `smoke_test_result.json` |

The notebook is **lightweight** — no embedded base64 image blobs.

## Image provenance

Same scene as Phase 9A/9B (`S2A_MSIL2A_20230815T095031_N0509_R079_T33UXP_20230815T155057`).
SHA256: `f330e6526a97bc3880bae5e75f45209bc98381042bb5ff0680d8fe3baa87f81b`

Raw URL (public repo):
`https://raw.githubusercontent.com/Sai-Vidyut/SatQuery-AI/main/experiments/phase9b_geochat/assets/sentinel2_smoketest.png`

## Optional

- Colab secret `HF_TOKEN` if Hugging Face model download requires auth.

## After success

**Stop here.** No LoRA training, BigEarthNet preprocessing, or production integration.

## Related

- `smoke_test.py` — same logic as a standalone script (local/cloud CLI)
- Phase 9A: `experiments/phase9a_geochat_smoketest/`
- Phase 9B adaptation: `experiments/phase9b_geochat_adaptation/`
