#!/usr/bin/env python3
"""Colab GeoChat uvicorn supervisor — captures exit code, PID, and full logs.

Starts uvicorn directly (no shell wrapper) so the real exit status is recorded.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parent.parent

sys.path.insert(0, str(SCRIPT_DIR))
from colab_diagnostics import (  # noqa: E402
    DEFAULT_EXIT_PATH,
    DEFAULT_LOG_PATH,
    DEFAULT_PID_PATH,
    format_process_health_line,
    get_gpu_memory_mb,
    is_pid_alive,
    run_nvidia_smi,
)

HEALTH_INTERVAL_S = 10.0


class _LogWriter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = path.open("a", encoding="utf-8", buffering=1)

    def write(self, text: str) -> None:
        self._fp.write(text)
        if not text.endswith("\n"):
            self._fp.write("\n")
        self._fp.flush()

    def close(self) -> None:
        self._fp.close()


def _cleanup_artifacts(
    *,
    pid_path: Path,
    exit_path: Path,
    log: _LogWriter,
) -> None:
    pid_path.unlink(missing_ok=True)
    exit_path.unlink(missing_ok=True)
    log.write("[supervisor] cleared stale pid/exit artifacts")


def _stream_output(pipe, log: _LogWriter) -> None:
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            log.write(line.rstrip("\n"))
    finally:
        pipe.close()


def _run_setup(setup_script: Path, log: _LogWriter) -> None:
    log.write(f"[supervisor] running setup: {setup_script} --setup-only")
    proc = subprocess.run(
        ["bash", str(setup_script), "--setup-only"],
        cwd=str(REPO_ROOT),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        for line in proc.stdout.splitlines():
            log.write(line)
    if proc.stderr:
        for line in proc.stderr.splitlines():
            log.write(line)
    if proc.returncode != 0:
        raise RuntimeError(f"Setup failed with exit code {proc.returncode}")


def _build_uvicorn_cmd(host: str, port: int) -> list[str]:
    return [
        sys.executable,
        "-u",
        "-m",
        "uvicorn",
        "geochat_service.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "info",
    ]


def _build_env() -> dict[str, str]:
    """Build uvicorn child environment, preserving GEOCHAT_SRC from the parent process."""
    env = os.environ.copy()
    # Colab launcher convention (matches colab_start.sh default when parent omitted export).
    geochat_src = env.get("GEOCHAT_SRC") or "/content/geochat"
    env["GEOCHAT_SRC"] = geochat_src
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("GEOCHAT_MODEL_ID", "MBZUAI/geochat-7B")
    env.setdefault("GEOCHAT_EAGER_LOAD", "true")
    env.setdefault("GEOCHAT_SERVICE_HOST", "0.0.0.0")
    env.setdefault("GEOCHAT_SERVICE_PORT", env.get("GEOCHAT_PORT", "8000"))
    env.pop("GEOCHAT_SERVICE_FAKE_ENGINE", None)
    pythonpath_parts = [geochat_src, str(SERVICE_ROOT)]
    existing = env.get("PYTHONPATH", "")
    if existing:
        pythonpath_parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def supervise(
    *,
    skip_setup: bool,
    log_path: Path,
    pid_path: Path,
    exit_path: Path,
    host: str,
    port: int,
) -> int:
    log = _LogWriter(log_path)
    child: subprocess.Popen[str] | None = None

    def _handle_signal(signum: int, _frame) -> None:
        log.write(f"[supervisor] received signal {signum}; forwarding to child")
        if child and child.poll() is None:
            try:
                child.send_signal(signum)
            except OSError:
                pass

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        _cleanup_artifacts(pid_path=pid_path, exit_path=exit_path, log=log)
        log.write("[supervisor] starting GeoChat uvicorn supervisor")
        log.write(f"[supervisor] log={log_path}")
        log.write(f"[supervisor] pid_file={pid_path}")
        log.write(f"[supervisor] exit_file={exit_path}")
        log.write(f"[supervisor] listen={host}:{port}")

        if not skip_setup:
            setup_script = SCRIPT_DIR / "colab_start.sh"
            if not setup_script.is_file():
                raise RuntimeError(f"Missing setup script: {setup_script}")
            _run_setup(setup_script, log)

        env = _build_env()
        cmd = _build_uvicorn_cmd(host, port)
        log.write(f"[supervisor] GEOCHAT_SRC={env['GEOCHAT_SRC']}")
        log.write("[supervisor] launching uvicorn (direct python subprocess, no shell)")
        log.write("[supervisor] cmd: " + " ".join(cmd))

        child = subprocess.Popen(
            cmd,
            cwd=str(SERVICE_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        pid_path.write_text(str(child.pid))
        log.write(f"[supervisor] wrote service pid={child.pid} -> {pid_path}")

        stream_thread = threading.Thread(
            target=_stream_output,
            args=(child.stdout, log),
            name="uvicorn-log-stream",
            daemon=True,
        )
        stream_thread.start()

        last_health = 0.0
        while True:
            returncode = child.poll()
            now = time.time()
            if now - last_health >= HEALTH_INTERVAL_S:
                log.write(format_process_health_line(pid_path))
                gpu = get_gpu_memory_mb()
                if gpu.get("available"):
                    log.write(
                        "[supervisor] gpu "
                        f"name={gpu.get('device_name')} "
                        f"alloc_mb={gpu.get('allocated_mb')} "
                        f"reserved_mb={gpu.get('reserved_mb')} "
                        f"total_mb={gpu.get('total_mb')}"
                    )
                last_health = now

            if returncode is not None:
                stream_thread.join(timeout=5.0)
                log.write(f"[supervisor] uvicorn exited with code {returncode}")
                exit_path.write_text(str(returncode))
                log.write(f"[supervisor] wrote exit code -> {exit_path}")
                pid_path.unlink(missing_ok=True)
                log.write("[supervisor] removed pid file (process exited)")
                log.write("--- nvidia-smi (post-exit) ---")
                for line in run_nvidia_smi().splitlines():
                    log.write(line)
                return int(returncode)

            if not is_pid_alive(child.pid):
                stream_thread.join(timeout=5.0)
                code = child.returncode if child.returncode is not None else -9
                log.write(f"[supervisor] child pid {child.pid} no longer alive (code={code})")
                exit_path.write_text(str(code))
                pid_path.unlink(missing_ok=True)
                return int(code)

            time.sleep(1.0)
    except Exception as exc:
        log.write(f"[supervisor] FATAL: {exc!r}")
        import traceback

        log.write(traceback.format_exc())
        exit_path.write_text("1")
        pid_path.unlink(missing_ok=True)
        return 1
    finally:
        log.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Colab GeoChat uvicorn supervisor")
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip colab_start.sh --setup-only (setup already completed).",
    )
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--pid-file", type=Path, default=DEFAULT_PID_PATH)
    parser.add_argument("--exit-file", type=Path, default=DEFAULT_EXIT_PATH)
    parser.add_argument("--host", default=os.environ.get("GEOCHAT_SERVICE_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GEOCHAT_PORT", os.environ.get("GEOCHAT_SERVICE_PORT", "8000"))),
    )
    args = parser.parse_args()

    code = supervise(
        skip_setup=args.skip_setup,
        log_path=args.log,
        pid_path=args.pid_file,
        exit_path=args.exit_file,
        host=args.host,
        port=args.port,
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
