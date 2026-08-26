"""Guardrail tests: nothing in this experiment fabricates VLM output,
BigEarthNet images, or checkpoint paths that don't exist.
"""
from pathlib import Path

import pytest

from phase9b.bigearthnet import (
    AdaptationExample,
    convert_to_adaptation_examples,
    parse_rows,
)
from phase9b.cloud_env import detect_cloud_environment


SAMPLE_ROW = {
    "ID": 1,
    "s1_name": "S1B_IW_GRDH_1SDV_20170612T165809_33UUP_26_57",
    "patch_id": "S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_26_57",
    "input": "Is water present?",
    "output": "no",
    "type": "binary",
    "category": "existence",
    "split": "test",
    "latitude": 48.11,
    "longitude": 12.74,
    "country": "Austria",
    "season": "Summer",
    "climate_zone": "Cold, no dry season, warm summer",
}


def test_adaptation_example_without_real_image_is_not_marked_trainable():
    rows = parse_rows([SAMPLE_ROW])
    examples = convert_to_adaptation_examples(rows, image_dir=None)
    assert examples[0].image_available is False
    assert examples[0].image_path is None


def test_adaptation_example_does_not_invent_a_path_for_nonexistent_dir(tmp_path: Path):
    fake_dir = tmp_path / "does_not_exist"
    rows = parse_rows([SAMPLE_ROW])
    examples = convert_to_adaptation_examples(rows, image_dir=fake_dir)
    assert examples[0].image_available is False


def test_local_environment_reports_no_cuda_gpu_it_does_not_have():
    """On the developer's 16GB Apple Silicon Mac (no CUDA), the detector
    must never report a fake GPU. This test documents Phase 9A's finding
    (local FP16 GeoChat inference is infeasible) is still respected: no
    code path here pretends CUDA exists when it doesn't.
    """
    report = detect_cloud_environment()
    if report.device_names:
        pytest.skip("Running on an actual GPU host; guardrail not applicable here.")
    assert report.device_names == []
    assert report.cuda_available is False


def test_checkpoint_path_handling_rejects_nonexistent_checkpoint(tmp_path: Path):
    from phase9b.geochat_io import build_vqa_prompt

    with pytest.raises(FileNotFoundError):
        build_vqa_prompt(
            system="sys",
            question="q?",
            image_path=tmp_path / "nonexistent_checkpoint_image.png",
        )
