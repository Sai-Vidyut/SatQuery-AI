# Cell 5 — Phase 9A/9B patches for geochat-7B Colab smoke test
import json
from pathlib import Path

config = json.loads(Path("/content/phase9b_geochat_smoke/smoke_config.json").read_text())
geochat_root = Path(config["geochat_src"])

# --- Patch 1: optional MPT import (Phase 9A) ---
init_py = geochat_root / "geochat" / "model" / "__init__.py"
text = init_py.read_text()

mpt_patch = """try:
    from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig
except ImportError:
    GeoChatMPTForCausalLM = None
    GeoChatMPTConfig = None"""

mpt_old = "from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig"

if "GeoChatMPTForCausalLM = None" in text:
    print("GeoChat MPT patch already applied.")
elif mpt_old in text:
    init_py.write_text(text.replace(mpt_old, mpt_patch))
    print("Applied GeoChat MPT optional-import patch.")
else:
    raise RuntimeError("Unexpected geochat/model/__init__.py layout — manual review required.")

# --- Patch 2: defer CLIP 336->504 interpolation until after checkpoint load (Phase 9B) ---
# GeoChat uses delay_load=True (geochat_arch.py). Upstream clip_encoder.py interpolates
# position embeddings to 504px (1297 tokens) inside __init__, but the HF checkpoint
# stores CLIP-336 weights (577 tokens). With low_cpu_mem_usage=True (8-bit LLM path),
# ignore_mismatched_sizes=True skips the mismatched param and leaves a meta tensor.
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

if defer_marker in clip_text:
    print("GeoChat CLIP defer-interpolation patch already applied.")
elif clip_old in clip_text:
    clip_encoder_py.write_text(clip_text.replace(clip_old, clip_new))
    print("Applied GeoChat CLIP defer-interpolation patch (577 tokens until post-load).")
else:
    raise RuntimeError(
        "Unexpected geochat/model/multimodal_encoder/clip_encoder.py layout — manual review required."
    )
