#!/usr/bin/env python3
"""GeoChat developer manager — local tooling only, not application runtime."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from geochat_dev.acceptance import run_real_provider_acceptance
from geochat_dev.client import GeoChatDevClient, print_json
from geochat_dev.config import load_config

MANUAL_START = """
Manual GeoChat GPU service (Colab/Kaggle) — not automatable from this repo:

1. Open Google Colab with a T4 GPU runtime.
2. Run services/geochat/colab_satquery_geochat.ipynb OR:
   !bash services/geochat/scripts/colab_start.sh
3. Wait until GET /health returns model_loaded=true and status=ok.
4. Start ngrok on port 8000 (Colab default):
   pip install -q pyngrok
   from pyngrok import ngrok
   conf.get_default().auth_token = "<NGROK_AUTHTOKEN from Colab Secrets>"
   print(ngrok.connect(8000, bind_tls=True))
5. Paste the printed GEOCHAT_* block into backend/.env on your Mac.
6. Run: python services/geochat/scripts/geochat_dev.py status

Kaggle has no checked-in Phase 16 notebook. Keeping a Kaggle kernel alive still
requires manual browser/API session management — do not expect Cursor to restart it.
""".strip()


def cmd_status(_: argparse.Namespace) -> int:
    config = load_config()
    client = GeoChatDevClient(config)
    status = client.status()
    print_json(status.to_dict())
    print()
    print(status.message)
    if config.env_file:
        print(f"env_file: {config.env_file} (loaded={config.env_file_loaded})")
    return 0 if status.real_mode_configured or not config.is_real_mode else 1


def cmd_health(_: argparse.Namespace) -> int:
    config = load_config()
    client = GeoChatDevClient(config)
    try:
        health = client.fetch_health()
    except Exception as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print_json(health)
    return 0 if health.get("model_loaded") and health.get("status") == "ok" else 1


def cmd_wait_ready(args: argparse.Namespace) -> int:
    config = load_config()
    client = GeoChatDevClient(config)
    status = client.wait_ready(timeout_s=args.timeout, poll_s=args.poll)
    print_json(status.to_dict())
    print()
    print(status.message)
    ready = status.model_loaded and bool(status.health and status.health.get("status") == "ok")
    return 0 if ready else 1


def cmd_smoke_test(args: argparse.Namespace) -> int:
    config = load_config()
    client = GeoChatDevClient(config)
    result = client.smoke_test(composite=args.composite, question=args.question)
    payload = {
        "status": result.status,
        "composite": result.composite,
        "model_name": result.model_name,
        "provider": result.provider,
        "answer_preview": (result.answer[:240] + "…") if result.answer and len(result.answer) > 240 else result.answer,
        "error": result.error,
    }
    print_json(payload)
    if result.status == "PASS":
        return 0
    if result.status == "BLOCKED":
        print(f"BLOCKED: {result.error}", file=sys.stderr)
        return 2
    print(f"FAIL: {result.error}", file=sys.stderr)
    return 1


def cmd_acceptance(_: argparse.Namespace) -> int:
    result = run_real_provider_acceptance()
    print_json(result.to_dict())
    print()
    print(result.message)
    if result.status == "PASS":
        return 0
    if result.status == "BLOCKED":
        return 2
    return 1


def cmd_start(_: argparse.Namespace) -> int:
    print(MANUAL_START)
    return 0


def cmd_stop(_: argparse.Namespace) -> int:
    print(
        "Stop is manual: terminate the Colab/Kaggle runtime or kill the supervised uvicorn process "
        "in that environment. Local Mac backend/frontend are separate from the GPU service."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GeoChat developer manager (local tooling only)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show configured provider, URL, and readiness")
    sub.add_parser("health", help="Fetch /health from configured GEOCHAT_SERVICE_URL")
    wait = sub.add_parser("wait-ready", help="Poll until model_loaded=true and status=ok")
    wait.add_argument("--timeout", type=float, default=600.0)
    wait.add_argument("--poll", type=float, default=5.0)

    smoke = sub.add_parser("smoke-test", help="Run a real /v1/vqa smoke test")
    smoke.add_argument("--composite", action="store_true", help="Use evidence BEFORE|AFTER composite")
    smoke.add_argument("--question", default=None)

    sub.add_parser("acceptance", help="Run full real-provider acceptance checks")
    sub.add_parser("start", help="Print manual Colab/Kaggle startup steps")
    sub.add_parser("stop", help="Print manual stop guidance")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "status": cmd_status,
        "health": cmd_health,
        "wait-ready": cmd_wait_ready,
        "smoke-test": cmd_smoke_test,
        "acceptance": cmd_acceptance,
        "start": cmd_start,
        "stop": cmd_stop,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
