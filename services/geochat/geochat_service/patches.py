"""Phase 9B GeoChat patches required before 8-bit T4 load."""

from __future__ import annotations

from pathlib import Path

DEFER_MARKER = "Phase 9B: defer 504 interpolation until after GeoChat checkpoint load"

# Exact __init__ delay_load=False else-branch block in upstream GeoChat clip_encoder.py
# (12-space indent). load_model() uses 8-space indent and is intentionally unchanged:
# Phase 9B never calls vision_tower.load_model() during service load.
CLIP_INIT_OLD = """            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            self.clip_interpolate_embeddings(image_size=504, patch_size=14)"""

CLIP_INIT_NEW = """            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            # Phase 9B: defer 504 interpolation until after GeoChat checkpoint load.
            # Checkpoint stores CLIP-336 position embeddings (577 tokens)."""

# Back-compat aliases used by tests.
CLIP_OLD = CLIP_INIT_OLD
CLIP_NEW = CLIP_INIT_NEW

MPT_OLD = "from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig"
MPT_PATCH = """try:
    from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig
except ImportError:
    GeoChatMPTForCausalLM = None
    GeoChatMPTConfig = None"""


def _clip_encoder_path(geochat_root: Path) -> Path:
    return geochat_root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"


def _init_branch_defers_interpolation(clip_text: str) -> bool:
    """True when __init__ delay_load branch no longer interpolates during construction.

    load_model() may still contain clip_interpolate_embeddings (8-space indent); Phase 9B
    service load never calls load_model() and instead uses finalize_vision_tower_for_504().
    """
    return DEFER_MARKER in clip_text and CLIP_INIT_OLD not in clip_text


def verify_geochat_patches(geochat_root: Path) -> None:
    """Raise if Phase 9B patches are not present on disk (matches notebook cell 5)."""
    clip_encoder_py = _clip_encoder_path(geochat_root)
    if not clip_encoder_py.is_file():
        raise RuntimeError(f"Missing GeoChat clip_encoder.py at {clip_encoder_py}")
    clip_text = clip_encoder_py.read_text()
    if not _init_branch_defers_interpolation(clip_text):
        if CLIP_INIT_OLD in clip_text:
            raise RuntimeError(
                "GeoChat clip_encoder.py __init__ still calls clip_interpolate_embeddings before "
                "checkpoint load. Phase 9B requires deferred interpolation until after checkpoint load."
            )
        if DEFER_MARKER not in clip_text:
            raise RuntimeError(
                "GeoChat CLIP defer-interpolation patch is not applied. "
                "Without it, CLIP position embeddings interpolate to 504px (1297 tokens) before "
                "checkpoint load, leaving meta tensors and causing load failure on T4. "
                f"Expected marker in {clip_encoder_py}"
            )
        raise RuntimeError(
            "GeoChat clip_encoder.py __init__ still calls clip_interpolate_embeddings. "
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

    clip_encoder_py = _clip_encoder_path(geochat_root)
    clip_text = clip_encoder_py.read_text()
    if CLIP_INIT_OLD in clip_text:
        clip_encoder_py.write_text(clip_text.replace(CLIP_INIT_OLD, CLIP_INIT_NEW))
    elif not _init_branch_defers_interpolation(clip_text):
        raise RuntimeError(
            "Unexpected geochat/model/multimodal_encoder/clip_encoder.py layout — "
            "cannot apply CLIP defer-interpolation patch."
        )

    verify_geochat_patches(geochat_root)
