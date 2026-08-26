#!/usr/bin/env python3
"""Fetch a small, deterministic BigEarthNet.txt metadata sample and convert
it into AdaptationExample records.

Does NOT download the 1.4GB parquet file. Uses the HF datasets-server rows
API to pull exactly `--num-rows` rows. Does NOT download any raw imagery —
image_available will be False for every example unless --image-dir is
given and populated separately (out of scope for Phase 9B, see
configs/dataset.yaml).

Usage:
    python scripts/prepare_bigearthnet_subset.py --num-rows 200 \
        --out data/bigearthnet_subset.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phase9b.bigearthnet import (  # noqa: E402
    convert_to_adaptation_examples,
    parse_rows,
    select_deterministic_subset,
)

DATASETS_SERVER_URL = (
    "https://datasets-server.huggingface.co/rows"
    "?dataset=BIFOLD-BigEarthNetv2-0%2FBigEarthNet.txt"
    "&config=default&split=all_data&offset={offset}&length={length}"
)


def fetch_rows(num_rows: int, page_size: int = 100) -> list[dict]:
    """Page through the datasets-server rows API without ever downloading
    the underlying parquet file.
    """
    rows: list[dict] = []
    offset = 0
    while len(rows) < num_rows:
        length = min(page_size, num_rows - len(rows))
        url = DATASETS_SERVER_URL.format(offset=offset, length=length)
        with urllib.request.urlopen(url, timeout=30) as resp:
            payload = json.loads(resp.read())
        page_rows = [r["row"] for r in payload.get("rows", [])]
        if not page_rows:
            break
        rows.extend(page_rows)
        offset += length
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-rows", type=int, default=200)
    parser.add_argument("--task-type", default=None, help="filter e.g. 'binary'")
    parser.add_argument("--split", default=None, help="filter e.g. 'test'")
    parser.add_argument(
        "--out", type=Path, default=Path("data/bigearthnet_subset.jsonl")
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=None,
        help="Optional local dir of already-acquired patch images (not provided by this script)",
    )
    args = parser.parse_args()

    print(f"[prepare] fetching {args.num_rows} rows via datasets-server API (no parquet download)...")
    raw_rows = fetch_rows(args.num_rows)
    print(f"[prepare] fetched {len(raw_rows)} raw rows")

    rows = parse_rows(raw_rows)
    subset = select_deterministic_subset(
        rows, max_rows=args.num_rows, task_type=args.task_type, split=args.split
    )
    examples = convert_to_adaptation_examples(subset, image_dir=args.image_dir)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for ex in examples:
            f.write(ex.model_dump_json() + "\n")

    n_with_images = sum(1 for e in examples if e.image_available)
    print(
        f"[prepare] wrote {len(examples)} examples to {args.out} "
        f"({n_with_images} with resolved local images, "
        f"{len(examples) - n_with_images} metadata-only)"
    )
    if n_with_images == 0:
        print(
            "[prepare] NOTE: 0 examples have image data. Raw BigEarthNet "
            "imagery acquisition is a separate, larger step (see "
            "configs/dataset.yaml) and was NOT performed by this script. "
            "This subset is metadata-only and is not yet trainable."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
