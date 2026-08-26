# Phase 9B — Cloud GeoChat Adaptation Experiment

Isolated research package. **Not imported by `backend/` or `frontend/`.**
Continues from Phase 9A (`experiments/phase9a_geochat_smoketest/`), which
found local FP16 GeoChat-7B inference infeasible on a 16GB Apple Silicon
Mac. This phase prepares a reproducible **cloud**-GPU experiment and stops
before any training.

## 1. Purpose

Establish, without training anything yet:

1. A hardware recommendation and a genuinely reproducible cloud environment.
2. The exact GeoChat-7B checkpoint/architecture setup, pinned.
3. A legitimate BigEarthNet.txt acquisition and small-subset strategy.
4. A documented, testable Sentinel-2 → GeoChat preprocessing pipeline.
5. One real GPU inference smoke test (VQA + scene description) on a real
   Sentinel-2 image.
6. A documented (not executed) LoRA/PEFT adaptation plan.
7. An evaluation interface for single-image VQA/captioning/grounding.
8. A `RemoteSensingVLM` interface defining the **future** SatQuery
   integration boundary — deliberately not wired into production.

## 2. Hardware requirements

Memory budget (fp16), derived from GeoChat's actual `config.json` (verified
in Phase 9A), not invented:

| Component | Size |
|---|---|
| LLaMA-7B weights | ~13.0 GB |
| CLIP ViT-L/14-336 vision tower | ~1.7 GB |
| mm_projector | ~0.03 GB |
| **Model subtotal** | **~14.7 GB** |
| + CUDA/framework overhead | ~0.5–1.5 GB |
| + inference activations (504×504 image, ~300 token generation) | ~0.5–1.5 GB |
| **Inference total** | **~16–18 GB** |
| + LoRA optimizer state + backward-pass activations | ~4–8 GB |
| **LoRA training total** | **~20–26 GB** |

This is why a single 16GB T4 (~15GB usable after ECC) is **not** assumed
sufficient — it is below even the inference-only estimate. See
`configs/cloud.yaml` for full profile documentation.

**Preferred:** NVIDIA A100 40GB (comfortable headroom for inference + LoRA
training in one environment). **Alternative:** L40S 24GB+ (covers
inference with headroom; LoRA needs rank ≤32 + gradient checkpointing).
Both are **paid** on every provider surveyed (Lambda, RunPod, Colab
Pay-As-You-Go/Pro+) — no free A100/L40S access was found as of Aug 2026.

## 3. Cloud setup (chosen for this phase)

**Chosen: Kaggle Notebooks, "GPU T4 x2"** — two NVIDIA T4 (16GB each, 32GB
combined), free, no credit card, 30 GPU-hours/week, 12-hour session cap.
Not a single 24GB+ GPU, but `device_map="auto"` (via `accelerate`) shards
the ~14.7GB of weights across both GPUs, giving real headroom for
inference that a single T4 would not have. **Not recommended for LoRA
training** (see `configs/cloud.yaml`) — that stays on the A100/L40S
profile for Phase 9C.

Alternatives evaluated and rejected for the primary path:
- Colab Free (single T4, ~15GB usable) — below our own inference estimate,
  margin too tight, GPU assignment not guaranteed.
- RunPod / Lambda A100 — paid, conflicts with `AGENTS.md`'s ₹0 budget
  unless the user explicitly accepts a small cost for Phase 9C.

**Kaggle access is driven via the Kaggle CLI (`kaggle kernels push`), using
a personal API token set via `KAGGLE_USERNAME` / `KAGGLE_KEY` environment
variables** (generated at kaggle.com/settings) — never hardcoded, never
committed. **This credential has not been provided in this session**, so
the GPU smoke test script (`scripts/cloud_smoke_test.py`) has been written
and is ready to run, but has **not yet been executed on an actual GPU**.
See "Smoke test" (§8) and the final report for the exact status.

## 4. Exact dependency versions

Pinned in `pyproject.toml`. Key versions and why:

| Package | Version | Reason |
|---|---|---|
| Python | ≥3.11 | matches backend/ convention |
| transformers | ==4.36.2 | Verified in Phase 9A to import `GeoChatLlamaForCausalLM` (legacy tuple KV cache API, still present at 4.36.x) |
| torch / torchvision | ≥2.1.0 / ≥0.16.0 (floor only) | Kaggle/Colab ship a CUDA-matched build; pinning an exact version risks breaking the CUDA/driver link — resolved version is recorded in the smoke-test result, not assumed |
| accelerate | ==0.25.0 | `device_map="auto"` multi-GPU sharding |
| peft | ==0.7.1 | planned LoRA adapter (Phase 9C) |
| sentencepiece, einops, einops-exts | pinned | required by GeoChat's own tokenizer/model code |

The official GeoChat repo's own `pyproject.toml` pins `torch==2.0.1`,
`transformers==4.31.0` — those exact wheels are impractical to source in
2026; 4.36.2 was empirically verified importable/structurally compatible in
Phase 9A (no training run yet validates numerical behavior at this pin).

## 5. Model acquisition

`MBZUAI/geochat-7B`, revision pinned in `configs/model.yaml`
(`cca91eb4c40d833c60579a5af95a7514181fe291`, from the HF API in Phase 9A).
14,126,079,376 bytes of fp16 weights (verified file listing). Architecture
class `GeoChatLlamaForCausalLM` (custom, requires cloning
`github.com/mbzuai-oryx/GeoChat`'s `geochat/` package — see Phase 9A's
patched copy for the one required fix: the unconditional MPT import must be
wrapped in `try/except ImportError`, since the MPT branch is unused by the
7B checkpoint and incompatible with modern `transformers`). Vision tower:
`openai/clip-vit-large-patch14-336`, interpolated to 504×504.

**No weights are committed to this repo.** They are downloaded at runtime
via `from_pretrained(...)`, cached by `huggingface_hub` in the cloud
session's cache dir.

## 6. Dataset acquisition — BigEarthNet.txt

**Verified facts** (see `configs/dataset.yaml` for full detail):

- `BIFOLD-BigEarthNetv2-0/BigEarthNet.txt` on Hugging Face contains **one
  1.4GB parquet file of TEXT ONLY**: 464,044 co-registered Sentinel-1/
  Sentinel-2 patch-ID pairs and ~9.6M question/answer/caption rows
  referencing those IDs. Columns: `ID, s1_name, patch_id, input, output,
  type, category, split, latitude, longitude, country, season,
  climate_zone`. **There is no pixel data in this repository.**
- Actual imagery must come from the official BigEarthNet v2.0 archive
  (~118GB total, Zenodo record `10.5281/zenodo.10891137`), converted via
  the dataset's own `rico-hdl` tool. No partial/small-sample official
  download mechanism exists.
- It IS multi-sensor (S1 SAR + S2 optical per patch), directly relevant to
  SatQuery's existing optical+SAR fusion capability, though this phase
  only targets optical VQA/captioning adaptation.

**What was actually done in Phase 9B:** `scripts/prepare_bigearthnet_subset.py`
pulls a small (`--num-rows`, default 200; demonstrated with 20) deterministic
sample via the **HF `datasets-server` rows REST API**, which returns
individual rows as JSON **without downloading the 1.4GB parquet file at
all**. This was run for real (see §13) and produced 20 real metadata rows.
**No raw BigEarthNet imagery was downloaded** — the 118GB archive is out of
scope for a controlled proof-of-concept per the task's explicit instruction.
Every `AdaptationExample` from this subset therefore has
`image_available=False`; the conversion script
(`scripts/convert_to_geochat_format.py`) correctly emits **zero** trainable
records and says so explicitly rather than fabricating image paths.

## 7. Dataset preprocessing

`src/phase9b/preprocessing.py` documents and implements, exactly (not
approximated):

1. **Band selection:** B04 (Red), B03 (Green), B02 (Blue) — standard
   Sentinel-2 true-color mapping.
2. **Reflectance scaling:** L2A surface-reflectance DN, stretched
   `[0, 3000]` → `[0, 255]` (standard true-color preview range).
3. **Square padding + resize:** `expand2square` (pad to square using the
   CLIP `image_mean` background color) then resize to 504×504, exactly
   reproducing GeoChat's own `mm_utils.py` behavior — avoids the
   aspect-ratio distortion a naive resize would introduce.
4. **Channel ordering:** HWC uint8 for storage; CHW float32 CLIP
   normalization is deferred to the model's own `CLIPImageProcessor` at
   inference time rather than reimplemented.
5. **Geospatial metadata preservation:** every visual PNG is saved
   alongside a `.metadata.json` (source, scene ID, acquisition time,
   WGS84 bounds, CRS, bands used, stretch range) — metadata is never
   discarded, only the pixel array is transformed for the VLM's visual
   input.

## 8. Smoke test

**Two scripts, run in sequence:**

1. `scripts/fetch_sentinel2_sample.py` — **executed for real** in this
   phase. Fetched a genuine Sentinel-2 L2A scene (`S2A_MSIL2A_20230815T0
   95031_N0509_R079_T33UXP_20230815T155057`, acquired 2023-08-15, near
   Vienna, Austria) via the existing authenticated Earth Engine workflow,
   applied the documented preprocessing, produced a real 504×504 RGB PNG
   (visually inspected — real agricultural field patterns, roads, a
   village, a small lake) and its metadata JSON. Explicitly labeled
   `REAL_SENTINEL2_SMOKETEST`, never described as BigEarthNet.
2. `scripts/cloud_smoke_test.py` — **written and validated to correctly
   detect and refuse a missing GPU (`require_cuda()` raised the expected
   error on the local Mac), but has NOT been executed on an actual CUDA
   GPU in this phase.** No Kaggle/Colab/RunPod credential was available in
   this session (see §3, §14). Running it requires:
   ```bash
   # inside a Kaggle GPU T4x2 notebook / Colab GPU runtime:
   pip install -e ".[cloud]"
   git clone https://github.com/mbzuai-oryx/GeoChat /tmp/GeoChat_src
   # apply the same try/except ImportError patch to GeoChat_src/geochat/model/__init__.py
   # as Phase 9A (see experiments/phase9a_geochat_smoketest/GeoChat_src/geochat/model/__init__.py)
   python scripts/cloud_smoke_test.py \
       --image data/real_sentinel2_smoketest/sentinel2_smoketest.png \
       --geochat-src /tmp/GeoChat_src \
       --out outputs/cloud_smoke_test_result.json
   ```
   The script records real GPU name/VRAM, load time, generation time, peak
   VRAM, image dimensions, exact prompts, and model answers into
   `outputs/cloud_smoke_test_result.json` (never fabricated — see
   `fabricated: false` field and `require_cuda()` guard).

## 9. Adaptation plan (documented, NOT executed)

See `configs/lora.yaml` for full reasoning. Summary: standard **LoRA**
(rank 16, alpha 32, dropout 0.05) on `q/k/v/o_proj` across all 32 layers
(~16.8M trainable params, ~0.24% of 7B), learning rate 2e-4, batch size 1
with gradient accumulation 16, 200-step proof-of-concept, adapter-only
checkpoints every 50 steps. QLoRA is a documented fallback only if training
must run on the free Kaggle T4x2 profile. **Nothing here has been trained.**

## 10. Evaluation plan

See `src/phase9b/evaluation.py`. `PredictionRecord` (JSONL) is the single
format for all tasks; `EvaluationMetric` is the output format. Planned
metrics: exact-match accuracy (VQA/binary/MCQ — BigEarthNet.txt, RSVQA),
BLEU-4/ROUGE-L/CIDEr (captioning — VRSBench), IoU@0.5 (grounding —
VRSBench), exact-match on VLM description of specialist-measured change
regions (CDVQA-style, change reasoning stays with the existing change
detector, not the VLM). **No benchmark data has been downloaded or
evaluated — this is an interface only.**

## 11. SatQuery integration boundary

`src/phase9b/vlm_interface.py` defines `RemoteSensingVLM` (ABC, same shape
as `app/adapters/semantic/base.py`'s `SemanticAnalyzer`) and `VLMResult`
(observable-only: answer, optional confidence, optional grounding box in
image-pixel space, model identity, runtime, provenance — no invented
evidence metrics, cannot override CVA/Dynamic World/SAR measurements).
**Not imported by `backend/app/`.** The documented (not implemented)
routing table: VQA/captioning/grounding → GeoChat; bi-temporal change →
existing change specialist (VLM may narrate an already-measured region,
never measure it itself); optical+SAR → existing fusion pipeline (VLM
output, if any, is advisory narrative only).

## 12. Known limitations

- Cloud GPU smoke test **not yet executed on real hardware** (no cloud
  credential available this session) — see §14.
- BigEarthNet raw imagery **not acquired** — every adaptation example is
  metadata-only; LoRA training cannot start until imagery is sourced
  (118GB official archive) or a smaller legitimate alternative is found.
- `transformers==4.36.2` vs. GeoChat's own `4.31.0` pin is **inferred**
  compatible (import-tested in Phase 9A) but **not numerically validated**
  against the original paper's reported outputs.
- LoRA compatibility is **inferred** from the upstream repo's own
  `finetune_lora.sh` script, not verified by an actual run here.
- Kaggle T4×2's 32GB is **pooled across two GPUs**, not one 24GB+ GPU —
  fine for sharded inference, explicitly not recommended for LoRA training.

## 13. Cost considerations

Everything executed in this phase was **free**: HF `datasets-server` API
calls, Earth Engine imagery fetch (existing free-tier authenticated
project), local CPU-only tests. The recommended A100/L40S environments for
LoRA training (Phase 9C) are **paid** on every provider surveyed — this
conflicts with `AGENTS.md`'s ₹0 budget and requires an explicit user
decision before Phase 9C proceeds. Kaggle's free GPU T4×2 tier (30h/week)
remains the ₹0-budget-compliant path for the inference smoke test.

## 14. Reproducibility instructions

```bash
cd experiments/phase9b_geochat_adaptation
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -q                      # 37 tests, no GPU required, ~3s

pip install -e ".[metadata]"          # only needed for optional full-parquet reads; not required below
python scripts/prepare_bigearthnet_subset.py --num-rows 200 --out data/bigearthnet_subset.jsonl
python scripts/convert_to_geochat_format.py --in data/bigearthnet_subset.jsonl --out data/bigearthnet_geochat_train.json

pip install -e ".[earth_engine]"
python scripts/fetch_sentinel2_sample.py --project <your-ee-project> --out-dir data/real_sentinel2_smoketest

# GPU-only, inside Kaggle/Colab/paid instance:
pip install -e ".[cloud]"
python scripts/cloud_smoke_test.py --image data/real_sentinel2_smoketest/sentinel2_smoketest.png --out outputs/cloud_smoke_test_result.json
```

No secrets are hardcoded anywhere in this package. Earth Engine credentials
reuse the backend's existing `EARTH_ENGINE_PROJECT` / service-account
mechanism (env vars only). A future Kaggle run requires `KAGGLE_USERNAME`
and `KAGGLE_KEY` as environment variables, never committed.
