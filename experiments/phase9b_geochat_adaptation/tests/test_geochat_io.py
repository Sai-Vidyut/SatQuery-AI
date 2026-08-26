from pathlib import Path

import pytest
from PIL import Image

from phase9b.geochat_io import IMAGE_TOKEN, build_vqa_prompt, load_and_validate_image


def test_build_vqa_prompt_contains_image_token_and_question(tmp_path: Path):
    img_path = tmp_path / "img.png"
    Image.new("RGB", (10, 10)).save(img_path)
    prompt = build_vqa_prompt(
        system="System text.", question="What is here?", image_path=img_path
    )
    assert IMAGE_TOKEN in prompt.text
    assert "What is here?" in prompt.text
    assert prompt.text.strip().endswith("ASSISTANT:")
    assert prompt.image_path == img_path


def test_build_vqa_prompt_rejects_missing_image(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        build_vqa_prompt(
            system="sys", question="q?", image_path=tmp_path / "nope.png"
        )


def test_build_vqa_prompt_rejects_empty_question(tmp_path: Path):
    img_path = tmp_path / "img.png"
    Image.new("RGB", (10, 10)).save(img_path)
    with pytest.raises(ValueError):
        build_vqa_prompt(system="sys", question="   ", image_path=img_path)


def test_load_and_validate_image_accepts_correct_size(tmp_path: Path):
    img_path = tmp_path / "img.png"
    Image.new("RGB", (504, 504)).save(img_path)
    loaded = load_and_validate_image(img_path, expected_px=504)
    assert loaded.size == (504, 504)


def test_load_and_validate_image_rejects_wrong_size(tmp_path: Path):
    img_path = tmp_path / "img.png"
    Image.new("RGB", (300, 300)).save(img_path)
    with pytest.raises(ValueError):
        load_and_validate_image(img_path, expected_px=504)
