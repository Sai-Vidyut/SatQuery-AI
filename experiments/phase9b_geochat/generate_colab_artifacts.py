#!/usr/bin/env python3
"""Build a lightweight multi-cell Colab notebook (no embedded base64)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CELLS_DIR = ROOT / "notebook_cells"
OUT_IPYNB = ROOT / "colab_geochat_smoke_test.ipynb"

CELL_FILES = [
    "01_environment.py",
    "02_install_dependencies.py",
    "03_clone_geochat.py",
    "04_fetch_sentinel2_image.py",
    "05_patch_geochat.py",
    "06_load_model.py",
    "07_run_inference.py",
    "08_write_results.py",
]

INTRO_MARKDOWN = """# Phase 9B — GeoChat-7B Colab Smoke Test

**Runtime:** Google Colab → **T4 GPU** (Runtime → Change runtime type)

Runs genuine `MBZUAI/geochat-7B` inference on a real Sentinel-2 L2A image.
Does not train. Does not touch SatQuery production code.

## Cells
1. Verify Python / CUDA / GPU / CPU RAM (`nvidia-smi`)
2. Clean dependency install (removes conflicting Colab packages; does **not** reinstall torch)
3. Clone GeoChat source
4. Download smoke-test Sentinel-2 PNG from GitHub (upload fallback if needed)
5. Apply Phase 9A MPT patch + Phase 9B CLIP defer-interpolation patch
6. Pre-load diagnostics + checkpoint inspection + **8-bit** GeoChat load (deferred CLIP 504)
7. Run one VQA inference
8. Write `smoke_test_result.json`

If the kernel dies during cell 6, open `/content/phase9b_geochat_smoke/pre_load_diagnostic.json`
in the Colab file browser — it is written **before** model weights are loaded.

Optional: set Colab secret `HF_TOKEN` if Hugging Face model download requires auth.
"""


def _code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "source": [line + "\n" for line in source.splitlines()],
        "outputs": [],
        "execution_count": None,
    }


def build_notebook() -> dict:
    cells: list[dict] = [
        {"cell_type": "markdown", "metadata": {}, "source": [INTRO_MARKDOWN]},
    ]
    for name in CELL_FILES:
        path = CELLS_DIR / name
        if not path.exists():
            raise FileNotFoundError(path)
        cells.append(_code_cell(path.read_text()))
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "T4"},
        },
        "cells": cells,
    }


def inspect_notebook(nb: dict, path: Path) -> dict:
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    sizes = []
    has_base64_blob = False
    for i, cell in enumerate(code_cells, 1):
        text = "".join(cell["source"])
        sizes.append((i, len(text)))
        if "EMBEDDED_SENTINEL2_B64" in text or len(text) > 50_000:
            if "base64" in text.lower() and len(text) > 50_000:
                has_base64_blob = True
    largest = max(sizes, key=lambda x: x[1])
    return {
        "notebook_path": str(path),
        "file_size_bytes": path.stat().st_size,
        "file_size_kb": round(path.stat().st_size / 1024, 1),
        "code_cell_count": len(code_cells),
        "markdown_cell_count": sum(1 for c in nb["cells"] if c["cell_type"] == "markdown"),
        "largest_code_cell_index": largest[0],
        "largest_code_cell_chars": largest[1],
        "contains_huge_base64_payload": has_base64_blob,
        "per_code_cell_chars": sizes,
    }


def validate_notebook_sources(nb: dict) -> None:
    """Static checks before writing the Colab notebook."""
    code_by_file = {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        for name in CELL_FILES:
            if src.startswith(f"# Cell {CELL_FILES.index(name) + 1}"):
                code_by_file[name] = src
                break

    cell5 = code_by_file.get("05_patch_geochat.py", "")
    cell6 = code_by_file.get("06_load_model.py", "")
    if "defer 504 interpolation" not in cell5:
        raise ValueError("Cell 5 must patch clip_encoder defer-interpolation")
    if '"ignore_mismatched_sizes"' in cell6.split("LOAD_KWARGS", 1)[-1][:400]:
        raise ValueError("Cell 6 must not use ignore_mismatched_sizes in LOAD_KWARGS")
    for line in cell6.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "vision_tower.load_model()" in stripped:
            raise ValueError("Cell 6 must not call vision_tower.load_model() after from_pretrained")
    if "finalize_vision_tower_for_504" not in cell6:
        raise ValueError("Cell 6 must call finalize_vision_tower_for_504")


def main() -> None:
    nb = build_notebook()
    validate_notebook_sources(nb)
    OUT_IPYNB.write_text(json.dumps(nb, indent=1))
    report = inspect_notebook(nb, OUT_IPYNB)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
