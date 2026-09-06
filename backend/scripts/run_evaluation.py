#!/usr/bin/env python3
"""Run Phase 6 catalog evaluation cases (live EE gated by EE_REAL_EVALUATION)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from evaluation.reports import render_markdown_report
from evaluation.runner import EvaluationRunner, load_cases, records_to_json


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run SatQuery Phase 6 evaluation cases")
    parser.add_argument(
        "--cases",
        type=Path,
        default=BACKEND_ROOT / "evaluation" / "cases" / "catalog_cases.json",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON records to path")
    parser.add_argument("--markdown", type=Path, default=None, help="Write markdown summary")
    args = parser.parse_args()

    if os.environ.get("EE_REAL_EVALUATION", "").lower() not in {"1", "true", "yes"}:
        print(
            "EE_REAL_EVALUATION is not set — skipping live run.\n"
            "Set IMAGERY_PROVIDER=earth_engine and EE_REAL_EVALUATION=true to execute against Earth Engine.",
            file=sys.stderr,
        )
        cases = load_cases(args.cases)
        print(f"Loaded {len(cases)} evaluation case(s) from {args.cases}")
        return 0

    runner = EvaluationRunner()
    records = await runner.run_all(load_cases(args.cases))
    payload = records_to_json(records)
    print(payload)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown_report(records), encoding="utf-8")
        print(f"Wrote {args.markdown}", file=sys.stderr)

    failed = [r for r in records if r.status == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
