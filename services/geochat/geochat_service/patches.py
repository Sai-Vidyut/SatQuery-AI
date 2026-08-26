"""Phase 9B GeoChat patches required before 8-bit T4 load."""

from __future__ import annotations

from pathlib import Path


def apply_geochat_patches(geochat_root: Path) -> None:
    """Apply verified Phase 9B patches to a cloned GeoChat repository."""
    init_py = geochat_root / "geochat" / "model" / "__init__.py"
    text = init_py.read_text()
    mpt_patch = """try:
    from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig
except ImportError:
    GeoChatMPTForCausalLM = None
    GeoChatMPTConfig = None"""
    mpt_old = "from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig"
    if "GeoChatMPTForCausalLM = None" not in text and mpt_old in text:
        init_py.write_text(text.replace(mpt_old, mpt_patch))

    clip_encoder_py = geochat_root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    clip_text = clip_encoder_py.read_text()
    defer_marker = "Phase 9B: defer 504 interpolation until after GeoChat checkpoint load"
    clip_old = """            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            self.clip_interpolate_embeddings(image_size=504, patch_size=14)"""
    clip_new = """            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            # Phase 9B: defer 504 interpolation until after GeoChat checkpoint load.
            # Checkpoint stores CLIP-336 position embeddings (577 tokens)."""
    if defer_marker not in clip_text and clip_old in clip_text:
        clip_encoder_py.write_text(clip_text.replace(clip_old, clip_new))
