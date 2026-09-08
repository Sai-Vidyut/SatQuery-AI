"""Deterministic before/after composite for real-provider smoke tests."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SMOKE_PNG = REPO_ROOT / "experiments" / "phase9b_geochat" / "assets" / "sentinel2_smoketest.png"
LABEL_HEIGHT = 28


def build_evidence_composite_smoke(
    *,
    smoke_png: Path | None = None,
    panel_size: int = 256,
) -> bytes:
    """Build a labeled BEFORE|AFTER composite from the known smoke PNG."""
    source = smoke_png or DEFAULT_SMOKE_PNG
    if not source.exists():
        raise FileNotFoundError(f"Smoke PNG not found: {source}")

    base = Image.open(source).convert("RGB")
    base = base.resize((panel_size, panel_size))
    before = base.copy()
    after = base.copy()

    # Slight tint on AFTER panel so real inference has a visible difference cue.
    after_pixels = after.load()
    for y in range(after.height):
        for x in range(after.width):
            r, g, b = after_pixels[x, y]
            after_pixels[x, y] = (min(r + 18, 255), max(g - 8, 0), max(b - 8, 0))

    panel_w = before.width + after.width
    canvas = Image.new("RGB", (panel_w, before.height + LABEL_HEIGHT), color=(16, 20, 26))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((8, 6), "BEFORE", fill=(220, 230, 240), font=font)
    draw.text((before.width + 8, 6), "AFTER", fill=(220, 230, 240), font=font)
    canvas.paste(before, (0, LABEL_HEIGHT))
    canvas.paste(after, (before.width, LABEL_HEIGHT))

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()
