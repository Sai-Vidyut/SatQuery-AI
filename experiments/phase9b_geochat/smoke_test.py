#!/usr/bin/env python3
"""Phase 9B — GeoChat-7B Colab / cloud GPU smoke test (research only).

Runs end-to-end on a CUDA GPU (designed for Google Colab Tesla T4, 15 GB VRAM).
Does NOT load GeoChat on the Mac. Does NOT touch backend/frontend.

Usage (Colab):
    Upload colab_geochat_smoke_test.ipynb (generate via generate_colab_artifacts.py).

Usage (CLI on GPU host):
    python smoke_test.py
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import traceback
import hashlib
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration (Phase 9A / 9B verified)
# ---------------------------------------------------------------------------
MODEL_ID = "MBZUAI/geochat-7B"
TRANSFORMERS_VERSION = "4.36.2"
ACCELERATE_VERSION = "0.25.0"
SENTENCEPIECE_VERSION = "0.1.99"
EINOPS_VERSION = "0.6.1"
EINOPS_EXTS_VERSION = "0.0.4"
GEOCHAT_REPO = "https://github.com/mbzuai-oryx/GeoChat.git"
MIN_VRAM_GB = 14.0  # fp16 model ~13.2 GB + inference headroom
QUESTION = (
    "Describe the main land-cover types and objects visible in this satellite image."
)
PROMPT_SYSTEM = (
    "A chat between a curious user and an artificial intelligence assistant. "
    "The assistant gives helpful, detailed, and polite answers to the user's questions."
)
WORK_DIR = Path(os.environ.get("PHASE9B_WORK_DIR", "/content/phase9b_geochat_smoke"))
RESULT_FILENAME = "smoke_test_result.json"
IMAGE_FILENAME = "sentinel2_smoketest.png"
IMAGE_URL = (
    "https://raw.githubusercontent.com/Sai-Vidyut/SatQuery-AI/main/"
    "experiments/phase9b_geochat/assets/sentinel2_smoketest.png"
)
IMAGE_SHA256 = "f330e6526a97bc3880bae5e75f45209bc98381042bb5ff0680d8fe3baa87f81b"

IMAGE_METADATA = {
    "source": "COPERNICUS/S2_SR_HARMONIZED (Google Earth Engine)",
    "scene_id": "S2A_MSIL2A_20230815T095031_N0509_R079_T33UXP_20230815T155057",
    "acquisition_time_iso": "2023-08-15T09:57:24.627000+00:00",
    "bands": ["B4 (Red)", "B3 (Green)", "B2 (Blue)"],
    "scaling": "surface reflectance DN, stretched [0, 3000] -> [0, 255]",
    "aoi_wgs84": [
        16.546090477803443,
        48.164067553000365,
        16.65390952219656,
        48.23593244699964,
    ],
    "output_dimensions_px": 504,
    "label": "REAL_SENTINEL2_SMOKETEST",
    "provenance": (
        "Same AOI/scene as Phase 9A/9B fetch_sentinel2_sample.py (Vienna mixed "
        "urban/agricultural Sentinel-2 L2A). Served from GitHub raw URL or local assets/."
    ),
    "sha256": IMAGE_SHA256,
}


def log(msg: str) -> None:
    print(f"[colab_smoke] {msg}", flush=True)


def write_result(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    log(f"wrote {path}")


def fail(stage: str, exc: BaseException, partial: dict | None = None) -> None:
    payload = {
        "status": "FAILED",
        "failure_stage": stage,
        "error": str(exc),
        "traceback": traceback.format_exc(),
        "fabricated": False,
        "model_loaded": False,
    }
    if partial:
        payload.update(partial)
    out = WORK_DIR / RESULT_FILENAME
    write_result(out, payload)
    log(f"FAILED at stage={stage}: {exc}")
    raise SystemExit(1) from exc


def vram_snapshot() -> dict:
    import torch

    if not torch.cuda.is_available():
        return {"available": False}
    idx = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(idx)
    total = props.total_memory / (1024**3)
    allocated = torch.cuda.memory_allocated(idx) / (1024**3)
    reserved = torch.cuda.memory_reserved(idx) / (1024**3)
    return {
        "device_index": idx,
        "device_name": props.name,
        "total_gb": round(total, 3),
        "allocated_gb": round(allocated, 3),
        "reserved_gb": round(reserved, 3),
        "free_gb_estimate": round(total - reserved, 3),
    }


def verify_environment(result: dict) -> None:
    import torch

    result["python_version"] = platform.python_version()
    result["platform"] = platform.platform()
    result["torch_version"] = torch.__version__
    result["cuda_available"] = torch.cuda.is_available()
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA not available. In Colab: Runtime → Change runtime type → T4 GPU."
        )
    result["gpu_before_load"] = vram_snapshot()
    if result["gpu_before_load"]["total_gb"] < MIN_VRAM_GB:
        raise RuntimeError(
            f"GPU VRAM {result['gpu_before_load']['total_gb']:.1f} GB is below "
            f"the {MIN_VRAM_GB:.0f} GB minimum for GeoChat-7B fp16 inference."
        )
    log(
        f"environment OK: Python {result['python_version']}, "
        f"torch {result['torch_version']}, GPU {result['gpu_before_load']['device_name']} "
        f"({result['gpu_before_load']['total_gb']:.1f} GB)"
    )


def install_dependencies() -> None:
    """Install GeoChat inference deps only. Keep Colab's CUDA-matched torch."""
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if hf_token:
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
        log("HF_TOKEN detected in environment (not logged).")
    pkgs = [
        f"transformers=={TRANSFORMERS_VERSION}",
        f"accelerate=={ACCELERATE_VERSION}",
        f"sentencepiece=={SENTENCEPIECE_VERSION}",
        f"einops=={EINOPS_VERSION}",
        f"einops-exts=={EINOPS_EXTS_VERSION}",
        "pillow>=10.0.0",
        "huggingface_hub>=0.25.0",
    ]
    log("installing inference dependencies (not reinstalling torch)...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", *pkgs],
    )


def setup_geochat_source(work: Path) -> Path:
    src = work / "GeoChat_src"
    if not (src / "geochat").is_dir():
        log(f"cloning GeoChat from {GEOCHAT_REPO} ...")
        subprocess.check_call(["git", "clone", "--depth", "1", GEOCHAT_REPO, str(src)])
    init_py = src / "geochat" / "model" / "__init__.py"
    text = init_py.read_text()
    patch = '''try:
    from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig
except ImportError:
    GeoChatMPTForCausalLM = None
    GeoChatMPTConfig = None'''
    if "GeoChatMPTForCausalLM = None" not in text:
        log("patching geochat/model/__init__.py (optional MPT import, Phase 9A)")
        old = (
            "from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig"
        )
        if old in text:
            text = text.replace(old, patch)
            init_py.write_text(text)
        else:
            raise RuntimeError("unexpected GeoChat __init__.py layout — patch failed")

    clip_encoder_py = src / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    clip_text = clip_encoder_py.read_text()
    defer_marker = "Phase 9B: defer 504 interpolation until after GeoChat checkpoint load"
    clip_old = """            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            self.clip_interpolate_embeddings(image_size=504, patch_size=14)"""
    clip_new = """            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            # Phase 9B: defer 504 interpolation until after GeoChat checkpoint load.
            # Checkpoint stores CLIP-336 position embeddings (577 tokens)."""
    if defer_marker not in clip_text:
        log("patching clip_encoder.py (defer CLIP 504 interpolation, Phase 9B)")
        if clip_old not in clip_text:
            raise RuntimeError("unexpected clip_encoder.py layout — patch failed")
        clip_encoder_py.write_text(clip_text.replace(clip_old, clip_new))
    return src


def load_sentinel2_image(work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    out = work / IMAGE_FILENAME
    if not out.exists():
        here = Path(__file__).resolve().parent
        local_png = here / "assets" / IMAGE_FILENAME
        if local_png.exists():
            out.write_bytes(local_png.read_bytes())
        else:
            log(f"downloading smoke image from {IMAGE_URL}")
            urllib.request.urlretrieve(IMAGE_URL, out)
    from PIL import Image

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    if digest != IMAGE_SHA256:
        raise ValueError(f"SHA256 mismatch: got {digest}, expected {IMAGE_SHA256}")
    img = Image.open(out).convert("RGB")
    if img.size != (504, 504):
        raise ValueError(f"expected 504x504 RGB, got {img.size}")
    log(f"loaded real Sentinel-2 smoke image: {out} ({img.size[0]}x{img.size[1]})")
    return out


def _finalize_vision_tower_for_504(vision_tower) -> None:
    pe = vision_tower.vision_tower.vision_model.embeddings.position_embedding.weight
    if getattr(pe, "is_meta", False):
        raise RuntimeError("vision_tower position_embedding still on meta device after checkpoint load")
    n_pos = int(pe.shape[0])
    if n_pos == 577:
        log("interpolating CLIP position embeddings 336px (577) -> 504px (1297)...")
        vision_tower.clip_interpolate_embeddings(image_size=504, patch_size=14)
    elif n_pos != 1297:
        raise RuntimeError(f"unexpected position_embedding rows: {n_pos}")
    vision_tower.is_loaded = True


def load_geochat_model(geochat_src: Path, result: dict):
    import torch
    from transformers import AutoTokenizer

    sys.path.insert(0, str(geochat_src))
    from geochat.constants import IMAGE_TOKEN_INDEX
    from geochat.mm_utils import process_images_demo, tokenizer_image_token
    from geochat.model.language_model.geochat_llama import GeoChatLlamaForCausalLM

    log("loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=False)

    # fp16 CLI path: defer CLIP 504 interpolation until after checkpoint load (cell 5 patch).
    log("loading GeoChatLlamaForCausalLM (fp16, single-GPU)...")
    t0 = time.time()
    try:
        model = GeoChatLlamaForCausalLM.from_pretrained(
            MODEL_ID,
            low_cpu_mem_usage=False,
            torch_dtype=torch.float16,
        )
        model = model.to("cuda")
        vision_tower = model.get_vision_tower()
        _finalize_vision_tower_for_504(vision_tower)
        vision_tower.to(dtype=torch.float16)
        image_processor = vision_tower.image_processor
        model.eval()
    except torch.cuda.OutOfMemoryError as e:
        raise RuntimeError(f"CUDA OOM during model load: {e}") from e
    except Exception as e:
        raise RuntimeError(f"model load failed: {e}") from e

    load_s = time.time() - t0
    result["model_load_time_s"] = round(load_s, 2)
    result["model_loaded"] = True
    result["gpu_after_load"] = vram_snapshot()
    result["peak_vram_gb_after_load"] = round(
        torch.cuda.max_memory_allocated() / (1024**3), 3
    )
    log(
        f"model loaded in {load_s:.1f}s, peak VRAM "
        f"{result['peak_vram_gb_after_load']:.2f} GB"
    )
    return model, tokenizer, image_processor, tokenizer_image_token, IMAGE_TOKEN_INDEX


def run_inference(
    *,
    model,
    tokenizer,
    image_processor,
    tokenizer_image_token,
    image_token_index: int,
    image_path: Path,
    result: dict,
) -> None:
    import torch
    from PIL import Image

    device = torch.device("cuda")
    raw_image = Image.open(image_path).convert("RGB")
    image_tensor = process_images_demo([raw_image], image_processor)
    image_tensor = image_tensor.to(device=device, dtype=torch.float16)

    prompt = f"{PROMPT_SYSTEM} USER: <image>\n{QUESTION} ASSISTANT:"
    input_ids = (
        tokenizer_image_token(prompt, tokenizer, image_token_index, return_tensors="pt")
        .unsqueeze(0)
        .to(device)
    )

    log("running GeoChat inference...")
    t0 = time.time()
    try:
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=image_tensor,
                do_sample=False,
                temperature=1.0,
                max_new_tokens=200,
                use_cache=True,
            )
    except torch.cuda.OutOfMemoryError as e:
        raise RuntimeError(f"CUDA OOM during inference: {e}") from e
    except Exception as e:
        raise RuntimeError(f"inference failed: {e}") from e

    gen_s = time.time() - t0
    answer = tokenizer.decode(
        output_ids[0, input_ids.shape[1] :], skip_special_tokens=True
    ).strip()
    if not answer:
        raise RuntimeError("inference returned an empty answer")

    result["inference"] = {
        "question": QUESTION,
        "prompt": prompt,
        "answer": answer,
        "generation_time_s": round(gen_s, 2),
    }
    result["peak_vram_gb_after_inference"] = round(
        torch.cuda.max_memory_allocated() / (1024**3), 3
    )
    log(f"inference done in {gen_s:.1f}s")
    log(f"ANSWER: {answer}")


def main() -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    result: dict = {
        "phase": "9B",
        "artifact": "colab_geochat_smoke_test",
        "model": MODEL_ID,
        "image_metadata": IMAGE_METADATA,
        "fabricated": False,
        "model_loaded": False,
    }
    t_start = time.time()

    try:
        import torch  # noqa: F401 — verify preinstalled in Colab

        verify_environment(result)
    except Exception as e:
        fail("environment", e, result)

    try:
        install_dependencies()
    except Exception as e:
        fail("dependency", e, result)

    try:
        geochat_src = setup_geochat_source(WORK_DIR)
    except Exception as e:
        fail("dependency", e, result)

    try:
        image_path = load_sentinel2_image(WORK_DIR)
        result["image_path"] = str(image_path)
    except Exception as e:
        fail("image", e, result)

    try:
        model, tokenizer, image_processor, tit, iti = load_geochat_model(geochat_src, result)
    except Exception as e:
        fail("model_loading", e, result)

    try:
        if result["gpu_after_load"]["free_gb_estimate"] < 0.3:
            raise RuntimeError(
                f"VRAM headroom too low after load "
                f"({result['gpu_after_load']['free_gb_estimate']:.2f} GB free)"
            )
    except Exception as e:
        fail("vram", e, result)

    try:
        run_inference(
            model=model,
            tokenizer=tokenizer,
            image_processor=image_processor,
            tokenizer_image_token=tit,
            image_token_index=iti,
            image_path=image_path,
            result=result,
        )
    except Exception as e:
        fail("inference", e, result)

    result["status"] = "PASSED"
    result["total_runtime_s"] = round(time.time() - t_start, 2)
    result["gpu_used"] = result["gpu_before_load"]["device_name"]
    out = WORK_DIR / RESULT_FILENAME
    write_result(out, result)
    log("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
