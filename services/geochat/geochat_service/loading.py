"""Phase 9B-aligned GeoChat model loading (shared with inference service)."""

from __future__ import annotations

import gc
import sys
from pathlib import Path
from typing import Any

from geochat_service.config import LOAD_STRATEGY
from geochat_service.patches import apply_geochat_patches, verify_geochat_patches

# Matches experiments/phase9b_geochat/notebook_cells/06_load_model.py LOAD_KWARGS.
# Do NOT add ignore_mismatched_sizes — it skips mismatched position_embedding weights
# and leaves meta tensors when low_cpu_mem_usage=True.
PHASE9B_LOAD_KWARGS = {
    "device_map": "auto",
    "load_in_8bit": True,
    "low_cpu_mem_usage": True,
}


def _checkpoint(message: str) -> None:
    print(f"[geochat] {message}", flush=True)


def finalize_vision_tower_for_504(vision_tower) -> dict[str, Any]:
    """Post-load CLIP 336/577 -> 504/1297 handling (Phase 9B cell 6)."""
    pe = vision_tower.vision_tower.vision_model.embeddings.position_embedding.weight
    if getattr(pe, "is_meta", False):
        raise RuntimeError(
            "vision_tower position_embedding is still on meta device after checkpoint load. "
            "Ensure the Phase 9B clip_encoder defer-interpolation patch is applied."
        )
    n_pos = int(pe.shape[0])
    if n_pos == 577:
        _checkpoint("applying deferred CLIP interpolation (577 -> 1297 tokens)")
        vision_tower.clip_interpolate_embeddings(image_size=504, patch_size=14)
        action = "interpolated_577_to_1297"
    elif n_pos == 1297:
        _checkpoint("vision tower already at 504px resolution (1297 position tokens)")
        action = "already_1297"
    else:
        raise RuntimeError(f"Unexpected position_embedding rows: {n_pos} (expected 577 or 1297)")
    vision_tower.is_loaded = True
    n_pos_after = int(
        vision_tower.vision_tower.vision_model.embeddings.position_embedding.weight.shape[0]
    )
    return {"position_tokens_before": n_pos, "position_tokens_after": n_pos_after, "action": action}


def load_geochat_runtime(
    *,
    model_id: str,
    geochat_src: Path,
    hf_token: str | None = None,
) -> dict[str, Any]:
    """Load tokenizer + model using the proven Phase 9B sequence. Returns runtime dict."""
    import torch
    from transformers import AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for GeoChat inference service.")

    geochat_root = geochat_src.resolve()
    if not (geochat_root / "geochat").is_dir():
        raise RuntimeError(f"GEOCHAT_SRC does not contain geochat package: {geochat_root}")

    _checkpoint("applying Phase 9B GeoChat patches")
    apply_geochat_patches(geochat_root)
    verify_geochat_patches(geochat_root)

    if str(geochat_root) not in sys.path:
        sys.path.insert(0, str(geochat_root))

    if hf_token:
        import os

        os.environ.setdefault("HF_TOKEN", hf_token)
        os.environ.setdefault("HUGGINGFACE_HUB_TOKEN", hf_token)

    # Purge any stale geochat modules so patched on-disk sources are imported.
    for name in list(sys.modules):
        if name == "geochat" or name.startswith("geochat."):
            del sys.modules[name]

    from geochat.model.language_model.geochat_llama import GeoChatLlamaForCausalLM

    gc.collect()
    torch.cuda.empty_cache()

    _checkpoint("loading tokenizer")
    tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=False)

    _checkpoint(f"loading GeoChat checkpoint ({LOAD_STRATEGY})")
    _checkpoint(
        "load kwargs: "
        f"device_map={PHASE9B_LOAD_KWARGS['device_map']!r}, "
        f"load_in_8bit={PHASE9B_LOAD_KWARGS['load_in_8bit']!r}, "
        f"low_cpu_mem_usage={PHASE9B_LOAD_KWARGS['low_cpu_mem_usage']!r}"
    )
    model = GeoChatLlamaForCausalLM.from_pretrained(model_id, **PHASE9B_LOAD_KWARGS)
    _checkpoint("checkpoint loaded")

    # Do NOT call vision_tower.load_model() — reloads CLIP from scratch (Phase 9B cell 6).
    _checkpoint("materializing vision tower")
    vision_tower = model.get_vision_tower()
    vision_report = finalize_vision_tower_for_504(vision_tower)
    vision_tower.to(device="cuda", dtype=torch.float16)
    image_processor = vision_tower.image_processor

    _checkpoint("model.eval()")
    model.eval()

    device = torch.device("cuda")
    for param in model.parameters():
        if param.device.type == "cuda":
            device = param.device
            break

    gpu_name = torch.cuda.get_device_name(device.index or 0)
    _checkpoint("model ready")

    return {
        "model": model,
        "tokenizer": tokenizer,
        "image_processor": image_processor,
        "device": device,
        "load_strategy": LOAD_STRATEGY,
        "gpu_name": gpu_name,
        "vision_tower_report": vision_report,
    }
