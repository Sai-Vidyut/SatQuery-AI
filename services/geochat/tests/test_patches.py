"""Tests for Phase 9B GeoChat patch application (no GPU)."""

from __future__ import annotations

from pathlib import Path

import pytest

from geochat_service.patches import (
    CLIP_INIT_NEW,
    CLIP_INIT_OLD,
    CLIP_NEW,
    CLIP_OLD,
    DEFER_MARKER,
    apply_geochat_patches,
    verify_geochat_patches,
)

# Minimal excerpt from mbzuai-oryx/GeoChat clip_encoder.py: __init__ (12-space) and
# load_model() (8-space) both call clip_interpolate_embeddings — only __init__ is patched.
UPSTREAM_CLIP_ENCODER = """\
class CLIPVisionTower(nn.Module):
    def clip_interpolate_embeddings(self, image_size=600, patch_size= 14):
        pass

    def __init__(self, vision_tower, args, delay_load=False):
        super().__init__()
        self.is_loaded = False
        self.vision_tower_name = vision_tower
        if not delay_load:
            self.load_model()
        else:
            self.cfg_only = CLIPVisionConfig.from_pretrained(self.vision_tower_name)
            self.image_processor = CLIPImageProcessor.from_pretrained(self.vision_tower_name)
            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            self.clip_interpolate_embeddings(image_size=504, patch_size=14)

    def load_model(self):
        self.image_processor = CLIPImageProcessor.from_pretrained(self.vision_tower_name)
        self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
        self.vision_tower.requires_grad_(False)
        self.clip_interpolate_embeddings(image_size=504, patch_size=14)
        self.is_loaded = True
"""


def _write_geochat_tree(root: Path, *, clip_body: str) -> None:
    init_py = root / "geochat" / "model" / "__init__.py"
    init_py.parent.mkdir(parents=True, exist_ok=True)
    init_py.write_text(
        "from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig\n"
    )
    clip_py = root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    clip_py.parent.mkdir(parents=True, exist_ok=True)
    clip_py.write_text(clip_body)


def test_verify_detects_unpatched_upstream_layout(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_geochat_tree(root, clip_body=UPSTREAM_CLIP_ENCODER)
    with pytest.raises(RuntimeError, match="__init__ still calls clip_interpolate_embeddings"):
        verify_geochat_patches(root)


def test_apply_patches_upstream_layout_and_verify_passes(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_geochat_tree(root, clip_body=UPSTREAM_CLIP_ENCODER)
    apply_geochat_patches(root)
    clip_text = (root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py").read_text()
    assert DEFER_MARKER in clip_text
    assert CLIP_INIT_OLD not in clip_text
    # load_model() path unchanged (not used by Phase 9B service load).
    assert "        self.clip_interpolate_embeddings(image_size=504, patch_size=14)" in clip_text
    verify_geochat_patches(root)


def test_apply_patches_twice_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_geochat_tree(root, clip_body=UPSTREAM_CLIP_ENCODER)
    apply_geochat_patches(root)
    clip_after_first = (
        root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    ).read_text()
    apply_geochat_patches(root)
    clip_after_second = (
        root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    ).read_text()
    assert clip_after_first == clip_after_second
    verify_geochat_patches(root)


def test_apply_patches_minimal_old_block(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_geochat_tree(root, clip_body=f"# header\n{CLIP_OLD}\n")
    apply_geochat_patches(root)
    verify_geochat_patches(root)
    assert CLIP_NEW in (
        root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    ).read_text()


def test_verify_patches_fails_when_marker_missing(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_geochat_tree(root, clip_body=f"# header\n{CLIP_OLD}\n")
    with pytest.raises(RuntimeError, match="__init__ still calls clip_interpolate_embeddings"):
        verify_geochat_patches(root)


def test_apply_patches_fails_on_unexpected_clip_layout(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_geochat_tree(root, clip_body="# unexpected upstream layout\npass\n")
    with pytest.raises(RuntimeError, match="clip_encoder.py layout"):
        apply_geochat_patches(root)
