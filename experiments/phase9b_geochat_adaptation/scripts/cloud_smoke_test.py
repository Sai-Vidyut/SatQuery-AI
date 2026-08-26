#!/usr/bin/env python3
"""GPU SMOKE TEST — genuine GeoChat-7B inference on a real Sentinel-2 image.

MUST be run inside a CUDA-capable environment (Kaggle GPU T4x2 notebook,
Colab GPU runtime, or a paid A100/L40S instance). Will refuse to run (raise,
not fabricate) if no CUDA GPU is detected — see phase9b.cloud_env.

This script does NOT train anything. It loads the base GeoChat-7B
checkpoint, runs exactly one VQA generation and one grounding-style
generation against one real image, and writes a fully-populated result
JSON with real timings/memory/answers, or an explicit error if it fails.

Expected input image: produced by scripts/fetch_sentinel2_sample.py
(REAL SENTINEL-2 SMOKE TEST, not BigEarthNet).

Usage (inside the GPU environment, after `pip install -e ".[cloud]"`):
    python scripts/cloud_smoke_test.py \
        --image data/real_sentinel2_smoketest/sentinel2_smoketest.png \
        --out outputs/cloud_smoke_test_result.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phase9b.cloud_env import detect_cloud_environment  # noqa: E402
from phase9b.config import load_model_config  # noqa: E402


def log(msg: str) -> None:
    print(f"[cloud_smoke_test] {msg}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument(
        "--question",
        default="Describe the land-cover and major objects visible in this image.",
    )
    parser.add_argument(
        "--vqa-question",
        default="What type of land cover dominates this image?",
    )
    parser.add_argument("--out", type=Path, default=Path("outputs/cloud_smoke_test_result.json"))
    parser.add_argument("--geochat-src", type=Path, default=None, help="Path to a cloned GeoChat repo's 'geochat' package parent dir")
    args = parser.parse_args()

    env = detect_cloud_environment()
    log(f"cloud environment: {env.model_dump()}")
    env.require_cuda()  # raises with a clear message if no GPU — never fakes a result

    if not args.image.exists():
        raise FileNotFoundError(
            f"{args.image} not found. Run scripts/fetch_sentinel2_sample.py first."
        )

    if args.geochat_src is not None:
        sys.path.insert(0, str(args.geochat_src))

    import torch
    from PIL import Image
    from transformers import AutoTokenizer

    from geochat.constants import IMAGE_TOKEN_INDEX
    from geochat.mm_utils import process_images_demo, tokenizer_image_token
    from geochat.model.language_model.geochat_llama import GeoChatLlamaForCausalLM

    model_cfg = load_model_config()
    model_path = model_cfg.hf_repo

    result: dict = {
        "gpu": {
            "device_names": env.device_names,
            "device_count": env.device_count,
            "total_vram_gb_per_device": [
                b / (1024**3) for b in env.total_vram_bytes_per_device
            ],
        },
        "torch_version": env.torch_version,
        "model": model_path,
    }

    t0 = time.time()
    log("loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)

    # NOTE on loading strategy (verified on Kaggle T4x2, transformers==4.36.2):
    #   1. `low_cpu_mem_usage=True` (with or without device_map="auto") forces
    #      transformers into its meta-tensor init path (_load_state_dict_into_meta_model).
    #      GeoChat's CLIPVisionTower.__init__ freshly loads
    #      openai/clip-vit-large-patch14-336 (577 position embeddings) and
    #      bicubic-interpolates it in-place to 1297 positions (504x504 input) as a
    #      real (non-meta) side effect. Meta-tensor loading breaks that interpolation
    #      and raises: ValueError: Trying to set a tensor of shape [577, 1024] in
    #      "weight" (which has shape [1297, 1024]).
    #   2. Setting low_cpu_mem_usage=False avoids meta-tensors, but transformers then
    #      does a strict shape check when applying the checkpoint's own vision-tower
    #      state dict (which still has the original, un-interpolated 577-shape CLIP
    #      weights) onto the already-interpolated 1297-shape module -> RuntimeError:
    #      size mismatch for position_embedding.weight.
    #   3. The checkpoint's vision tower is frozen (requires_grad_(False)) and never
    #      fine-tuned by GeoChat, so its weights are identical to the fresh CLIP
    #      checkpoint already loaded by CLIPVisionTower.__init__. `ignore_mismatched_sizes=True`
    #      correctly skips loading that one mismatched param (leaving the freshly
    #      interpolated 1297-shape values in place) while loading everything else
    #      (LLM + mm_projector) normally.
    log("loading GeoChatLlamaForCausalLM (fp16, single-GPU cuda:0, ignore_mismatched_sizes)...")
    t_load = time.time()
    model = GeoChatLlamaForCausalLM.from_pretrained(
        model_path,
        low_cpu_mem_usage=False,
        torch_dtype=torch.float16,
        ignore_mismatched_sizes=True,
    )
    model = model.to("cuda")
    result["model_load_time_s"] = time.time() - t_load

    vision_tower = model.get_vision_tower()
    if not vision_tower.is_loaded:
        vision_tower.load_model()
    vision_tower.to(dtype=torch.float16)
    image_processor = vision_tower.image_processor
    model.eval()

    result["total_load_time_s"] = time.time() - t0
    peak_vram_gb = torch.cuda.max_memory_allocated() / (1024**3)
    log(f"loaded in {result['total_load_time_s']:.1f}s, peak VRAM so far: {peak_vram_gb:.2f}GB")

    raw_image = Image.open(args.image).convert("RGB")
    result["image_dimensions_px"] = list(raw_image.size)
    image_tensor = process_images_demo([raw_image], image_processor)
    model_device = torch.device("cuda")
    image_tensor = image_tensor.to(device=model_device, dtype=torch.float16)

    def run_prompt(question: str) -> dict:
        prompt = model_cfg.build_prompt(question)
        input_ids = (
            tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt")
            .unsqueeze(0)
            .to(model_device)
        )
        t_gen = time.time()
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=image_tensor,
                do_sample=False,
                temperature=1.0,
                max_new_tokens=200,
                use_cache=True,
            )
        gen_s = time.time() - t_gen
        answer = tokenizer.decode(
            output_ids[0, input_ids.shape[1] :], skip_special_tokens=True
        ).strip()
        return {"prompt": prompt, "question": question, "answer": answer, "generation_time_s": gen_s}

    log("running scene-description prompt...")
    result["scene_description"] = run_prompt(args.question)
    log(f"ANSWER: {result['scene_description']['answer']}")

    log("running VQA prompt...")
    result["vqa"] = run_prompt(args.vqa_question)
    log(f"ANSWER: {result['vqa']['answer']}")

    result["peak_vram_gb"] = torch.cuda.max_memory_allocated() / (1024**3)
    result["image_source_label"] = "REAL_SENTINEL2_SMOKETEST"
    result["fabricated"] = False

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    log(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
