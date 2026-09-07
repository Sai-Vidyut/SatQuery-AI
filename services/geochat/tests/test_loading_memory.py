"""Tests for Colab-oriented GeoChat load memory caps."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def loading_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEOCHAT_COLAB_MEMORY_PROFILE", raising=False)
    monkeypatch.delenv("GEOCHAT_LOAD_MAX_MEMORY_GPU", raising=False)
    monkeypatch.delenv("GEOCHAT_LOAD_MAX_MEMORY_CPU", raising=False)
    monkeypatch.delenv("GEOCHAT_OFFLOAD_DIR", raising=False)
    import geochat_service.loading as loading

    return importlib.reload(loading)


def test_colab_profile_uses_cpu_cap_without_disk_key(
    loading_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEOCHAT_COLAB_MEMORY_PROFILE", "colab")
    caps = loading_module._resolve_load_max_memory()
    assert caps is not None
    assert caps["cpu"] == "2GiB"
    assert "disk" not in caps
    assert caps[0].endswith("GiB")


def test_explicit_cpu_env_includes_default_gpu_cap(
    loading_module, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEOCHAT_COLAB_MEMORY_PROFILE", "colab")
    monkeypatch.setenv("GEOCHAT_LOAD_MAX_MEMORY_CPU", "1GiB")
    caps = loading_module._resolve_load_max_memory()
    assert caps is not None
    assert caps["cpu"] == "1GiB"
    assert caps[0].endswith("GiB")
    assert "disk" not in caps


def test_offload_folder_when_colab_profile(loading_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEOCHAT_COLAB_MEMORY_PROFILE", "colab")
    monkeypatch.setenv("GEOCHAT_OFFLOAD_DIR", "/tmp/geochat_offload_test")
    folder = loading_module._resolve_offload_folder()
    assert folder is not None
    assert str(folder) == "/tmp/geochat_offload_test"


def test_colab_profile_disabled_explicitly(loading_module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEOCHAT_COLAB_MEMORY_PROFILE", "off")
    assert loading_module._colab_memory_profile_enabled() is False
    assert loading_module._resolve_offload_folder() is None
