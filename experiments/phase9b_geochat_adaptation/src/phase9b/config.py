"""Deterministic YAML config loading for the Phase 9B experiment.

No network access, no GPU required. Pure parsing + validation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "configs"


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: dict[str, Any]
    vision_tower: dict[str, Any]
    projector: dict[str, Any]
    tokenizer: dict[str, Any]
    prompt_template: dict[str, Any]

    @property
    def hf_repo(self) -> str:
        return self.model["name"]

    @property
    def hf_revision(self) -> str:
        return self.model["revision"]

    def build_prompt(self, question: str) -> str:
        tpl = self.prompt_template
        return tpl["format"].format(
            system=tpl["system"].strip(), question=question.strip()
        )


class CloudConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    profiles: dict[str, dict[str, Any]]
    selected_for_phase_9b: str
    selection_reason: str

    @property
    def selected_profile(self) -> dict[str, Any]:
        return self.profiles[self.selected_for_phase_9b]


class LoraConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: str
    target_modules: list[str]
    rank: int
    alpha: int
    dropout: float
    learning_rate: float
    batch_size: int
    gradient_accumulation_steps: int
    image_resolution_px: int


class DatasetConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: dict[str, Any]
    acquisition_strategy_for_poc: dict[str, Any]
    smoke_test_image_policy: str


def _load_yaml(filename: str) -> dict[str, Any]:
    path = CONFIGS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not parse to a mapping")
    return data


def load_model_config() -> ModelConfig:
    return ModelConfig.model_validate(_load_yaml("model.yaml"))


def load_cloud_config() -> CloudConfig:
    return CloudConfig.model_validate(_load_yaml("cloud.yaml"))


def load_lora_config() -> LoraConfig:
    return LoraConfig.model_validate(_load_yaml("lora.yaml"))


def load_dataset_config() -> DatasetConfig:
    return DatasetConfig.model_validate(_load_yaml("dataset.yaml"))
