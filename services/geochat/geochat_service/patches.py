"""Phase 9B GeoChat patches required before 8-bit T4 load."""

from __future__ import annotations

from pathlib import Path

DEFER_MARKER = "Phase 9B: defer 504 interpolation until after GeoChat checkpoint load"

CLIP_OLD = """            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            self.clip_interpolate_embeddings(image_size=504, patch_size=14)"""

CLIP_NEW = """            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            # Phase 9B: defer 504 interpolation until after GeoChat checkpoint load.
            # Checkpoint stores CLIP-336 position embeddings (577 tokens)."""

MPT_OLD = "from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig"
MPT_PATCH = """try:
    from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig
except ImportError:
    GeoChatMPTForCausalLM = None
    GeoChatMPTConfig = None"""


def verify_geochat_patches(geochat_root: Path) -> None:
    """Raise if Phase 9B patches are not present on disk (matches notebook cell 5)."""
    clip_encoder_py = geochat_root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    if not clip_encoder_py.is_file():
        raise RuntimeError(f"Missing GeoChat clip_encoder.py at {clip_encoder_py}")
    clip_text = clip_encoder_py.read_text()
    if DEFER_MARKER not in clip_text:
        raise RuntimeError(
            "GeoChat CLIP defer-interpolation patch is not applied. "
            "Without it, CLIP position embeddings interpolate to 504px (1297 tokens) before "
            "checkpoint load, leaving meta tensors and causing load failure on T4. "
            f"Expected marker in {clip_encoder_py}"
        )
    if "self.clip_interpolate_embeddings(image_size=504, patch_size=14)" in clip_text:
        raise RuntimeError(
            "GeoChat clip_encoder.py still calls clip_interpolate_embeddings in __init__. "
            "Phase 9B requires deferred interpolation until after checkpoint load."
        )

    init_py = geochat_root / "geochat" / "model" / "__init__.py"
    init_text = init_py.read_text()
    if "GeoChatMPTForCausalLM = None" not in init_text and MPT_OLD in init_text:
        raise RuntimeError(
            "GeoChat MPT optional-import patch is not applied. "
            f"Expected patched imports in {init_py}"
        )


def apply_geochat_patches(geochat_root: Path) -> None:
    """Apply verified Phase 9B patches to a cloned GeoChat repository (strict)."""
    init_py = geochat_root / "geochat" / "model" / "__init__.py"
    if not init_py.is_file():
        raise RuntimeError(f"Missing GeoChat package at {geochat_root / 'geochat'}")

    text = init_py.read_text()
    if "GeoChatMPTForCausalLM = None" in text:
        pass
    elif MPT_OLD in text:
        init_py.write_text(text.replace(MPT_OLD, MPT_PATCH))
    else:
        raise RuntimeError(
            "Unexpected geochat/model/__init__.py layout — cannot apply MPT patch."
        )

    clip_encoder_py = geochat_root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    clip_text = clip_encoder_py.read_text()
    if DEFER_MARKER in clip_text:
        pass
    elif CLIP_OLD in clip_text:
        clip_encoder_py.write_text(clip_text.replace(CLIP_OLD, CLIP_NEW))
    else:
        raise RuntimeError(
            "Unexpected geochat/model/multimodal_encoder/clip_encoder.py layout — "
            "cannot apply CLIP defer-interpolation patch."
        )

    verify_geochat_patches(geochat_root)
