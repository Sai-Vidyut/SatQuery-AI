import pytest

from phase9b.bigearthnet import (
    AdaptationExample,
    BigEarthNetTextRow,
    convert_to_adaptation_examples,
    parse_rows,
    select_deterministic_subset,
)

# Real sample rows, fetched from the HF datasets-server rows API
# (BIFOLD-BigEarthNetv2-0/BigEarthNet.txt, split=all_data, offset=0..5) on
# 2026-08-25, for schema/behavior testing only. Not a bulk dataset file.
REAL_SAMPLE_ROWS = [
    {
        "ID": 1,
        "s1_name": "S1B_IW_GRDH_1SDV_20170612T165809_33UUP_26_57",
        "patch_id": "S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_26_57",
        "input": "Would you say that any arable land lies next to pastures in the image?",
        "output": "yes",
        "type": "binary",
        "category": "adjacency",
        "split": "test",
        "latitude": 48.11003471465957,
        "longitude": 12.740300299577253,
        "country": "Austria",
        "season": "Summer",
        "climate_zone": "Cold, no dry season, warm summer",
    },
    {
        "ID": 3,
        "s1_name": "S1B_IW_GRDH_1SDV_20170612T165809_33UUP_26_57",
        "patch_id": "S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_26_57",
        "input": "Do pastures cover between 864000 square meters and 1008000 square meters of the image?",
        "output": "no",
        "type": "binary",
        "category": "area",
        "split": "test",
        "latitude": 48.11003471465957,
        "longitude": 12.740300299577253,
        "country": "Austria",
        "season": "Summer",
        "climate_zone": "Cold, no dry season, warm summer",
    },
]


def test_parse_rows_validates_schema():
    rows = parse_rows(REAL_SAMPLE_ROWS)
    assert len(rows) == 2
    assert isinstance(rows[0], BigEarthNetTextRow)
    assert rows[0].patch_id.startswith("S2A_MSIL2A")


def test_parse_rows_rejects_missing_column():
    bad_row = {k: v for k, v in REAL_SAMPLE_ROWS[0].items() if k != "patch_id"}
    with pytest.raises(Exception):
        parse_rows([bad_row])


def test_deterministic_subset_is_order_preserving_and_repeatable():
    rows = parse_rows(REAL_SAMPLE_ROWS)
    subset_a = select_deterministic_subset(rows, max_rows=1)
    subset_b = select_deterministic_subset(rows, max_rows=1)
    assert [r.ID for r in subset_a] == [r.ID for r in subset_b] == [1]


def test_deterministic_subset_filters_by_category_and_split():
    rows = parse_rows(REAL_SAMPLE_ROWS)
    subset = select_deterministic_subset(rows, max_rows=10, task_type="binary", split="test")
    assert len(subset) == 2


def test_convert_without_image_dir_marks_unavailable():
    rows = parse_rows(REAL_SAMPLE_ROWS)
    examples = convert_to_adaptation_examples(rows, image_dir=None)
    assert all(isinstance(e, AdaptationExample) for e in examples)
    assert all(not e.image_available for e in examples)
    assert all(e.image_path is None for e in examples)


def test_convert_with_missing_image_dir_still_marks_unavailable(tmp_path):
    rows = parse_rows(REAL_SAMPLE_ROWS)
    examples = convert_to_adaptation_examples(rows, image_dir=tmp_path)
    assert all(not e.image_available for e in examples)


def test_convert_resolves_real_existing_image(tmp_path):
    rows = parse_rows(REAL_SAMPLE_ROWS[:1])
    patch_file = tmp_path / f"{rows[0].patch_id}.png"
    patch_file.write_bytes(b"not a real image, just presence-tested")
    examples = convert_to_adaptation_examples(rows, image_dir=tmp_path)
    assert examples[0].image_available is True
    assert examples[0].image_path == str(patch_file)
