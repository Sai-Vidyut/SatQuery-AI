"""Tests for Phase 9B GeoChat patch application (no GPU)."""

from __future__ import annotations

from pathlib import Path

import pytest

from geochat_service.patches import (
    CLIP_NEW,
    CLIP_OLD,
    DEFER_MARKER,
    apply_geochat_patches,
    verify_geochat_patches,
)


def _write_minimal_geochat_tree(root: Path, *, patched_clip: bool) -> None:
    init_py = root / "geochat" / "model" / "__init__.py"
    init_py.parent.mkdir(parents=True, exist_ok=True)
    init_py.write_text(
        "from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig\n"
    )
    clip_py = root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    clip_py.parent.mkdir(parents=True, exist_ok=True)
    if patched_clip:
        clip_py.write_text(f"# header\n{CLIP_NEW}\n")
    else:
        clip_py.write_text(f"# header\n{CLIP_OLD}\n")


def test_apply_patches_strict_success(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_minimal_geochat_tree(root, patched_clip=False)
    apply_geochat_patches(root)
    verify_geochat_patches(root)
    assert DEFER_MARKER in (root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py").read_text()


def test_verify_patches_fails_when_clip_not_deferred(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_minimal_geochat_tree(root, patched_clip=False)
    with pytest.raises(RuntimeError, match="defer-interpolation patch"):
        verify_geochat_patches(root)


def test_apply_patches_fails_on_unexpected_clip_layout(tmp_path: Path) -> None:
    root = tmp_path / "geochat_src"
    _write_minimal_geochat_tree(root, patched_clip=False)
    clip_py = root / "geochat" / "model" / "multimodal_encoder" / "clip_encoder.py"
    clip_py.write_text("# unexpected upstream layout\npass\n")
    with pytest.raises(RuntimeError, match="clip_encoder.py layout"):
        apply_geochat_patches(root)
