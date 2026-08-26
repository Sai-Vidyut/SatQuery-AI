"""
PHASE 9A SMOKE TEST — WATCHDOG (temporary script, not part of SatQuery-AI).

Runs smoke_test_worker.py as a child process and polls its memory usage
(RSS) plus overall system available memory. Kills the child immediately if
either crosses an unsafe threshold, so we never risk freezing the host
machine (16GB unified memory, actively used for other work).

Usage: python watchdog.py
Exit behavior:
  - prints periodic memory status lines
  - if aborted, prints "WATCHDOG_ABORT" with the reason
  - if the worker finishes on its own, prints "WORKER_EXITED code=<n>"
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).parent

# This machine has 16GB unified memory. Leave real headroom for the OS,
# Cursor, and other running apps rather than pushing to the theoretical max.
MAX_WORKER_RSS_GB = 12.0
MIN_SYSTEM_AVAILABLE_GB = 1.5
POLL_INTERVAL_S = 2.0


def gb(bytes_val):
    return bytes_val / (1024 ** 3)


def main():
    python = sys.executable
    env = os.environ.copy()
    # All model artifacts (weights + CLIP tower) are already cached locally
    # from the earlier download step; force fully offline to avoid the
    # sandboxed network proxy interfering with a background subprocess.
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    proc = subprocess.Popen(
        [python, str(HERE / "smoke_test_worker.py")],
        cwd=str(HERE),
        env=env,
    )
    ps_proc = psutil.Process(proc.pid)

    peak_rss_gb = 0.0
    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                print(f"WORKER_EXITED code={ret} peak_rss_gb={peak_rss_gb:.2f}", flush=True)
                return ret

            try:
                rss_gb = gb(ps_proc.memory_info().rss)
                # NOTE: skip child-process enumeration — psutil.Process.children()
                # calls a system-wide pid listing that macOS sandbox denies
                # (sysctl permission error). The worker is single-process anyway.
            except psutil.NoSuchProcess:
                print("WORKER_EXITED code=unknown (process vanished)", flush=True)
                return -1

            peak_rss_gb = max(peak_rss_gb, rss_gb)
            avail_gb = gb(psutil.virtual_memory().available)

            print(
                f"[watchdog] worker_rss={rss_gb:.2f}GB peak={peak_rss_gb:.2f}GB "
                f"system_available={avail_gb:.2f}GB",
                flush=True,
            )

            if rss_gb > MAX_WORKER_RSS_GB:
                proc.kill()
                print(
                    f"WATCHDOG_ABORT reason=worker_rss_exceeded_{MAX_WORKER_RSS_GB}GB "
                    f"actual={rss_gb:.2f}GB",
                    flush=True,
                )
                return 137

            if avail_gb < MIN_SYSTEM_AVAILABLE_GB:
                proc.kill()
                print(
                    f"WATCHDOG_ABORT reason=system_available_below_{MIN_SYSTEM_AVAILABLE_GB}GB "
                    f"actual={avail_gb:.2f}GB",
                    flush=True,
                )
                return 137

            time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        proc.kill()
        raise


if __name__ == "__main__":
    sys.exit(main())
