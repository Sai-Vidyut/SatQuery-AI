"""Tests for Colab supervisor diagnostics helpers."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_diagnostics_module():
    spec = importlib.util.spec_from_file_location(
        "colab_diagnostics",
        _SCRIPTS_DIR / "colab_diagnostics.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["colab_diagnostics"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def diagnostics():
    return _load_diagnostics_module()


def test_startup_not_exited_when_supervisor_alive_without_service_pid(
    diagnostics,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid_path = tmp_path / "service.pid"
    exit_path = tmp_path / "service.exit"

    monkeypatch.setattr(diagnostics, "is_pid_alive", lambda pid: pid == 4242)

    assert diagnostics.service_startup_exited(
        pid_path=pid_path,
        exit_path=exit_path,
        supervisor_pid=4242,
        started_at=time.time(),
        grace_s=90.0,
    ) is False


def test_startup_exited_when_exit_file_recorded(diagnostics, tmp_path: Path) -> None:
    pid_path = tmp_path / "service.pid"
    exit_path = tmp_path / "service.exit"
    exit_path.write_text("1")

    assert diagnostics.service_startup_exited(
        pid_path=pid_path,
        exit_path=exit_path,
        supervisor_pid=4242,
        started_at=time.time(),
    ) is True


def test_startup_exited_after_grace_without_supervisor_or_service(
    diagnostics,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid_path = tmp_path / "service.pid"
    exit_path = tmp_path / "service.exit"

    monkeypatch.setattr(diagnostics, "is_pid_alive", lambda _pid: False)

    assert diagnostics.service_startup_exited(
        pid_path=pid_path,
        exit_path=exit_path,
        supervisor_pid=None,
        started_at=time.time() - 120.0,
        grace_s=90.0,
    ) is True


def test_startup_not_exited_during_grace_without_pids(
    diagnostics,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid_path = tmp_path / "service.pid"
    exit_path = tmp_path / "service.exit"

    monkeypatch.setattr(diagnostics, "is_pid_alive", lambda _pid: False)

    assert diagnostics.service_startup_exited(
        pid_path=pid_path,
        exit_path=exit_path,
        supervisor_pid=None,
        started_at=time.time(),
        grace_s=90.0,
    ) is False
