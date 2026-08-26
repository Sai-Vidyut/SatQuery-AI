from phase9b.config import (
    load_cloud_config,
    load_dataset_config,
    load_lora_config,
    load_model_config,
)


def test_model_config_loads():
    cfg = load_model_config()
    assert cfg.hf_repo == "MBZUAI/geochat-7B"
    assert cfg.hf_revision
    assert cfg.model["torch_dtype"] == "float16"


def test_model_config_build_prompt():
    cfg = load_model_config()
    prompt = cfg.build_prompt("What is this?")
    assert "<image>" in prompt
    assert "USER:" in prompt
    assert "ASSISTANT:" in prompt
    assert "What is this?" in prompt


def test_cloud_config_loads_and_selection_is_documented():
    cfg = load_cloud_config()
    assert cfg.selected_for_phase_9b in cfg.profiles
    assert cfg.selection_reason


def test_lora_config_loads():
    cfg = load_lora_config()
    assert cfg.method == "LoRA"
    assert cfg.rank > 0
    assert set(cfg.target_modules) >= {"q_proj", "v_proj"}


def test_dataset_config_loads():
    cfg = load_dataset_config()
    assert cfg.source["hf_repo"] == "BIFOLD-BigEarthNetv2-0/BigEarthNet.txt"
