"""BigEarthNet.txt metadata parsing and deterministic sample conversion.

IMPORTANT: This module handles TEXT METADATA ONLY (patch IDs, questions,
answers, coordinates). It does not download, fabricate, or synthesize any
pixel data. Converting a metadata row into a trainable GeoChat example
requires the corresponding real image bytes, which are obtained separately
(see scripts/prepare_bigearthnet_subset.py and configs/dataset.yaml). Rows
without a resolved local image path are marked `image_available=False` and
must never be silently treated as ready-to-train.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Verified column set from the HF datasets-server rows API
# (https://datasets-server.huggingface.co/rows?dataset=BIFOLD-BigEarthNetv2-0%2FBigEarthNet.txt),
# cross-checked against the dataset's own README "Parquet File Structure".
BEN_TXT_COLUMNS = (
    "ID",
    "s1_name",
    "patch_id",
    "input",
    "output",
    "type",
    "category",
    "split",
    "latitude",
    "longitude",
    "country",
    "season",
    "climate_zone",
)

BEN_TXT_TYPES = ("binary", "mcq", "captioning", "bounding box")


class BigEarthNetTextRow(BaseModel):
    """One row of BigEarthNet.txt metadata (text only, no pixels)."""

    model_config = ConfigDict(extra="forbid")

    ID: int
    s1_name: str
    patch_id: str
    input: str
    output: str
    type: str
    category: str
    split: str
    latitude: float
    longitude: float
    country: str
    season: str
    climate_zone: str


class AdaptationExample(BaseModel):
    """One row converted into the shape GeoChat's prompt template expects.

    `image_available` is the load-bearing honesty flag: this class can be
    constructed from metadata alone, but `image_path` is only set once the
    corresponding real BigEarthNet patch has actually been located on disk
    (see scripts/prepare_bigearthnet_subset.py). Nothing downstream may
    treat an example with image_available=False as trainable.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: int
    patch_id: str
    s1_name: str
    question: str
    reference_answer: str
    task_type: str
    category: str
    split: str
    image_available: bool = False
    image_path: str | None = None

    @classmethod
    def from_row(
        cls, row: BigEarthNetTextRow, image_path: Path | None = None
    ) -> "AdaptationExample":
        return cls(
            source_id=row.ID,
            patch_id=row.patch_id,
            s1_name=row.s1_name,
            question=row.input,
            reference_answer=row.output,
            task_type=row.type,
            category=row.category,
            split=row.split,
            image_available=image_path is not None,
            image_path=str(image_path) if image_path is not None else None,
        )


def parse_rows(raw_rows: list[dict]) -> list[BigEarthNetTextRow]:
    """Parse a list of raw dicts (e.g. from the datasets-server rows API,
    or a locally cached JSON sample) into validated rows.

    Deterministic and order-preserving. Raises on any row missing a
    required column rather than silently dropping it.
    """
    return [BigEarthNetTextRow.model_validate(r) for r in raw_rows]


def select_deterministic_subset(
    rows: list[BigEarthNetTextRow],
    *,
    max_rows: int,
    task_type: str | None = None,
    split: str | None = None,
) -> list[BigEarthNetTextRow]:
    """Deterministic (order-preserving, no randomness) subset selection.

    Filters are applied in a fixed order, then the first `max_rows` survivors
    are returned. Given the same input list and filters, this always
    produces the same output — required for reproducibility.
    """
    filtered = rows
    if task_type is not None:
        filtered = [r for r in filtered if r.type == task_type]
    if split is not None:
        filtered = [r for r in filtered if r.split == split]
    return filtered[:max_rows]


def convert_to_adaptation_examples(
    rows: list[BigEarthNetTextRow],
    *,
    image_dir: Path | None = None,
) -> list[AdaptationExample]:
    """Convert rows to AdaptationExample, resolving image_path if present.

    `image_dir` is expected to contain files named `{patch_id}.png` (or
    similar) once a real image acquisition step has populated it. If
    `image_dir` is None or the file doesn't exist, `image_available` stays
    False — this function never invents a path.
    """
    out: list[AdaptationExample] = []
    for row in rows:
        image_path: Path | None = None
        if image_dir is not None:
            candidate = image_dir / f"{row.patch_id}.png"
            if candidate.exists():
                image_path = candidate
        out.append(AdaptationExample.from_row(row, image_path=image_path))
    return out
