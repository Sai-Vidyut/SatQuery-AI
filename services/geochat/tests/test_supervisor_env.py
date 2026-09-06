"""Regression tests for Colab supervisor environment propagation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_supervisor_module():
    spec = importlib.util.spec_from_file_location(
        "colab_supervisor",
        _SCRIPTS_DIR / "colab_supervisor.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["colab_supervisor"] = module
    spec.loader.exec_module(module)
    return module


def test_build_env_propagates_geochat_src_from_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEOCHAT_SRC", "/tmp/custom-geochat")
    supervisor = _load_supervisor_module()
    env = supervisor._build_env()
    assert env["GEOCHAT_SRC"] == "/tmp/custom-geochat"
    assert "/tmp/custom-geochat" in env["PYTHONPATH"]


def test_build_env_sets_geochat_src_for_uvicorn_child_when_parent_omits_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEOCHAT_SRC", raising=False)
    supervisor = _load_supervisor_module()
    env = supervisor._build_env()
    assert env["GEOCHAT_SRC"] == "/content/geochat"
    assert "/content/geochat" in env["PYTHONPATH"]


def test_build_env_propagates_hf_token_to_uvicorn_child(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    supervisor = _load_supervisor_module()
    env = supervisor._build_env()
    assert env["HF_TOKEN"] == "test-token"
    assert env["HUGGINGFACE_HUB_TOKEN"] == "test-token"
