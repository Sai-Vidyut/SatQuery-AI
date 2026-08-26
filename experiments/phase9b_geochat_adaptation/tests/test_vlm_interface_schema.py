import pytest
from pydantic import ValidationError

from phase9b.vlm_interface import GroundingBox, RemoteSensingVLM, VLMResult, VLMTask


def test_vlm_result_requires_provenance_and_model_identity():
    result = VLMResult(
        task=VLMTask.VQA,
        answer="A river runs through cropland.",
        model_name="MBZUAI/geochat-7B",
        model_version="base",
        input_image_ids=["img-1"],
        runtime_ms=1234,
        provenance="MBZUAI/geochat-7B base, no adapter",
    )
    assert result.confidence is None
    assert result.grounding is None


def test_vlm_result_confidence_must_be_probability():
    with pytest.raises(ValidationError):
        VLMResult(
            task=VLMTask.VQA,
            answer="x",
            confidence=1.5,
            model_name="m",
            model_version="v",
            input_image_ids=["i"],
            runtime_ms=1,
            provenance="p",
        )


def test_vlm_result_rejects_extra_fields_like_invented_evidence_metrics():
    with pytest.raises(ValidationError):
        VLMResult(
            task=VLMTask.VQA,
            answer="x",
            model_name="m",
            model_version="v",
            input_image_ids=["i"],
            runtime_ms=1,
            provenance="p",
            change_area_km2=12.3,  # not a real field — must be rejected
        )


def test_grounding_box_is_image_space_not_geographic_by_default():
    box = GroundingBox(x_min=0.1, y_min=0.1, x_max=0.5, y_max=0.5)
    assert box.coordinate_space == "normalized_0_1_image_pixels"


def test_remote_sensing_vlm_is_abstract_and_cannot_be_instantiated():
    with pytest.raises(TypeError):
        RemoteSensingVLM()  # type: ignore[abstract]
