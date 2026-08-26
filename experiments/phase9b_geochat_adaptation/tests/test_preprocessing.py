import numpy as np
from PIL import Image

from phase9b.preprocessing import (
    GEOCHAT_INPUT_PX,
    SceneMetadata,
    bands_to_rgb_uint8,
    expand_to_square,
    prepare_geochat_visual_input,
    reflectance_dn_to_uint8,
    save_scene,
)


def test_reflectance_stretch_clips_and_scales():
    band = np.array([[-100, 0, 1500, 3000, 10000]], dtype=np.float32)
    out = reflectance_dn_to_uint8(band)
    assert out.dtype == np.uint8
    assert out[0, 0] == 0  # clipped negative -> 0
    assert out[0, 1] == 0
    assert out[0, 3] == 255  # at the max stretch bound
    assert out[0, 4] == 255  # clipped above max -> 255
    assert 0 < out[0, 2] < 255  # mid-range


def test_bands_to_rgb_uint8_shape_and_order():
    red = np.full((10, 10), 3000, dtype=np.float32)
    green = np.full((10, 10), 1500, dtype=np.float32)
    blue = np.full((10, 10), 0, dtype=np.float32)
    rgb = bands_to_rgb_uint8(red, green, blue)
    assert rgb.shape == (10, 10, 3)
    assert rgb[0, 0, 0] == 255  # R channel from `red`
    assert rgb[0, 0, 2] == 0  # B channel from `blue`


def test_bands_to_rgb_uint8_rejects_mismatched_shapes():
    red = np.zeros((10, 10), dtype=np.float32)
    green = np.zeros((5, 5), dtype=np.float32)
    blue = np.zeros((10, 10), dtype=np.float32)
    try:
        bands_to_rgb_uint8(red, green, blue)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_expand_to_square_pads_wide_image():
    img = Image.new("RGB", (100, 50), (1, 2, 3))
    squared = expand_to_square(img, (9, 9, 9))
    assert squared.size == (100, 100)


def test_expand_to_square_noop_for_already_square():
    img = Image.new("RGB", (50, 50), (1, 2, 3))
    squared = expand_to_square(img, (9, 9, 9))
    assert squared.size == (50, 50)


def test_prepare_geochat_visual_input_produces_expected_size():
    rgb = np.zeros((300, 200, 3), dtype=np.uint8)
    result = prepare_geochat_visual_input(rgb)
    assert result.size == (GEOCHAT_INPUT_PX, GEOCHAT_INPUT_PX)
    assert result.mode == "RGB"


def test_prepare_geochat_visual_input_rejects_bad_shape():
    bad = np.zeros((10, 10), dtype=np.uint8)  # missing channel dim
    try:
        prepare_geochat_visual_input(bad)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_save_scene_writes_image_and_metadata(tmp_path):
    rgb = np.full((20, 20, 3), 128, dtype=np.uint8)
    metadata = SceneMetadata(
        source="test",
        scene_id="scene-1",
        acquisition_time_iso="2023-06-01T00:00:00+00:00",
        bounds_wgs84=(1.0, 2.0, 3.0, 4.0),
        crs="EPSG:4326",
        bands_used=("B04", "B03", "B02"),
        reflectance_stretch=(0, 3000),
    )
    image_path, metadata_path = save_scene(rgb, metadata, tmp_path, stem="test_scene")
    assert image_path.exists()
    assert metadata_path.exists()
    loaded = Image.open(image_path)
    assert loaded.size == (20, 20)
    saved_meta = metadata_path.read_text()
    assert "scene-1" in saved_meta
    assert "bounds_wgs84" in saved_meta
