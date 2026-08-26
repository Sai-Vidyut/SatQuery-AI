# Cell 4 — obtain real Sentinel-2 smoke-test image (no base64 in notebook)
import hashlib
import json
import urllib.request
from pathlib import Path

from PIL import Image

config = json.loads(Path("/content/phase9b_geochat_smoke/smoke_config.json").read_text())
image_path = Path(config["image_path"])
expected_sha = config["image_sha256"]
image_url = config["image_url"]


def validate_png(path: Path) -> None:
    img = Image.open(path).convert("RGB")
    if img.size != (504, 504):
        raise ValueError(f"expected 504x504 RGB PNG, got {img.size}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha:
        raise ValueError(
            f"SHA256 mismatch for {path.name}: got {digest}, expected {expected_sha}"
        )
    print(f"Validated {path} ({img.size[0]}x{img.size[1]}, sha256 OK)")


if image_path.exists():
    print(f"Image already exists at {image_path}, re-validating...")
    validate_png(image_path)
else:
    print(f"Downloading smoke-test image from:\n  {image_url}")
    try:
        urllib.request.urlretrieve(image_url, image_path)
        validate_png(image_path)
        print("Downloaded and validated image from GitHub raw URL.")
    except Exception as download_err:
        print(
            "GitHub download failed (image may not be pushed to main yet).\n"
            f"  Error: {download_err}\n"
            "Falling back to Colab file upload — select ONLY:\n"
            "  experiments/phase9b_geochat/assets/sentinel2_smoketest.png"
        )
        try:
            from google.colab import files
        except ImportError as e:
            raise RuntimeError(
                "Image download failed and Colab upload API is unavailable."
            ) from e

        uploaded = files.upload()
        if not uploaded:
            raise RuntimeError("No file uploaded.")
        if len(uploaded) != 1:
            raise RuntimeError(
                f"Upload exactly one PNG file; got {list(uploaded)}"
            )
        name, data = next(iter(uploaded.items()))
        if not name.lower().endswith(".png"):
            raise RuntimeError(f"Expected a .png file, got {name!r}")
        image_path.write_bytes(data)
        validate_png(image_path)
        print(f"Uploaded image saved to {image_path}")
