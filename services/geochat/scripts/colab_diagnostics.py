"""Shared Colab process/GPU diagnostics for GeoChat service supervision."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_LOG_PATH = Path("/content/geochat_server.log")
DEFAULT_PID_PATH = Path("/content/geochat_server.pid")
DEFAULT_EXIT_PATH = Path("/content/geochat_server.exit")


@dataclass
class ProcessState:
    pid: int | None
    pid_file_exists: bool
    alive: bool
    rss_mb: float | None
    status: str | None


def read_pid(pid_path: Path = DEFAULT_PID_PATH) -> int | None:
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text().strip())
    except (OSError, ValueError):
        return None


def read_exit_code(exit_path: Path = DEFAULT_EXIT_PATH) -> int | None:
    if not exit_path.exists():
        return None
    try:
        text = exit_path.read_text().strip()
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_process_state(pid_path: Path = DEFAULT_PID_PATH) -> ProcessState:
    pid = read_pid(pid_path)
    if pid is None:
        return ProcessState(
            pid=None,
            pid_file_exists=pid_path.exists(),
            alive=False,
            rss_mb=None,
            status=None,
        )
    alive = is_pid_alive(pid)
    rss_mb: float | None = None
    status: str | None = None
    if alive:
        try:
            import psutil

            proc = psutil.Process(pid)
            rss_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
            status = proc.status()
        except Exception:
            pass
    return ProcessState(
        pid=pid,
        pid_file_exists=True,
        alive=alive,
        rss_mb=rss_mb,
        status=status,
    )


def get_gpu_memory_mb() -> dict[str, Any]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {"available": False}
        idx = torch.cuda.current_device()
        allocated = torch.cuda.memory_allocated(idx)
        reserved = torch.cuda.memory_reserved(idx)
        props = torch.cuda.get_device_properties(idx)
        return {
            "available": True,
            "device_index": idx,
            "device_name": props.name,
            "allocated_mb": round(allocated / (1024 * 1024), 1),
            "reserved_mb": round(reserved / (1024 * 1024), 1),
            "total_mb": round(props.total_memory / (1024 * 1024), 1),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def run_nvidia_smi() -> str:
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            check=False,
            capture_output=True,
            text=True,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or "(nvidia-smi produced no output)"
    except FileNotFoundError:
        return "(nvidia-smi not found)"
    except Exception as exc:
        return f"(nvidia-smi failed: {exc})"


def log_tail(log_path: Path = DEFAULT_LOG_PATH, n: int = 200) -> str:
    if not log_path.exists():
        return "(log file missing)"
    lines = log_path.read_text(errors="replace").splitlines()
    return "\n".join(lines[-n:])


def service_startup_exited(
    *,
    pid_path: Path = DEFAULT_PID_PATH,
    exit_path: Path = DEFAULT_EXIT_PATH,
    supervisor_pid: int | None = None,
    started_at: float | None = None,
    grace_s: float = 90.0,
) -> bool:
    """Return True when the supervised uvicorn process has definitively exited.

    During the grace window after ``started_at``, do not treat a missing service PID
    as a crash while the supervisor is still starting uvicorn.
    """
    exit_code = read_exit_code(exit_path)
    if exit_code is not None:
        return True

    service = get_process_state(pid_path)
    supervisor_alive = is_pid_alive(supervisor_pid) if supervisor_pid is not None else False

    if service.pid is not None and not service.alive:
        return True

    if supervisor_alive or service.alive:
        return False

    if started_at is None:
        return False
    return (time.time() - started_at) >= grace_s


def format_process_health_line(pid_path: Path = DEFAULT_PID_PATH) -> str:
    state = get_process_state(pid_path)
    gpu = get_gpu_memory_mb()
    parts = [
        f"pid={state.pid}",
        f"alive={state.alive}",
    ]
    if state.rss_mb is not None:
        parts.append(f"rss_mb={state.rss_mb}")
    if state.status:
        parts.append(f"status={state.status}")
    if gpu.get("available"):
        parts.append(
            f"gpu_alloc_mb={gpu.get('allocated_mb')} "
            f"gpu_reserved_mb={gpu.get('reserved_mb')}"
        )
    else:
        parts.append("gpu=unavailable")
    return "[supervisor] " + " ".join(parts)


def print_failure_report(
    *,
    log_path: Path = DEFAULT_LOG_PATH,
    pid_path: Path = DEFAULT_PID_PATH,
    exit_path: Path = DEFAULT_EXIT_PATH,
    log_lines: int = 200,
    title: str = "GeoChat service failure report",
) -> None:
    exit_code = read_exit_code(exit_path)
    state = get_process_state(pid_path)
    print(f"=== {title} ===")
    print(f"exit_code:     {exit_code if exit_code is not None else '(not recorded)'}")
    print(f"pid_file:      {pid_path} (exists={pid_path.exists()})")
    print(f"service_pid:   {state.pid}")
    print(f"process_alive: {state.alive}")
    if state.rss_mb is not None:
        print(f"process_rss_mb: {state.rss_mb}")
    if state.status:
        print(f"process_status: {state.status}")
    print(f"exit_file:     {exit_path} (exists={exit_path.exists()})")
    print(f"log_file:      {log_path} (exists={log_path.exists()})")
    print("\n--- ps (geochat/uvicorn/python) ---")
    try:
        subprocess.run(
            ["ps", "aux"],
            check=False,
        )
    except Exception as exc:
        print(f"(ps failed: {exc})")
    print("\n--- nvidia-smi ---")
    print(run_nvidia_smi())
    print(f"\n--- last {log_lines} log lines ---")
    print(log_tail(log_path, log_lines))
