# Cell 1 — environment verification (pre-dependency-install baseline)
import json
import platform
import subprocess
from pathlib import Path

import torch

WORK_DIR = Path("/content/phase9b_geochat_smoke")
WORK_DIR.mkdir(parents=True, exist_ok=True)


def cpu_ram_snapshot() -> dict:
    """Linux /proc/meminfo snapshot (works on Colab without extra packages)."""
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            key, value = line.split(":", 1)
            info[key.strip()] = int(value.strip().split()[0])  # kB
    total_kb = info.get("MemTotal", 0)
    avail_kb = info.get("MemAvailable", info.get("MemFree", 0))
    return {
        "total_gb": round(total_kb / (1024**2), 2),
        "available_gb": round(avail_kb / (1024**2), 2),
        "used_gb": round((total_kb - avail_kb) / (1024**2), 2),
    }


SMOKE_CONFIG = {
    "phase": "9B",
    "work_dir": str(WORK_DIR),
    "model_id": "MBZUAI/geochat-7B",
    "geochat_repo": "https://github.com/mbzuai-oryx/GeoChat.git",
    "geochat_src": str(WORK_DIR / "GeoChat_src"),
    "image_path": str(WORK_DIR / "sentinel2_smoketest.png"),
    "result_path": str(WORK_DIR / "smoke_test_result.json"),
    "diagnostic_path": str(WORK_DIR / "pre_load_diagnostic.json"),
    "load_report_path": str(WORK_DIR / "load_report.json"),
    "min_vram_gb_8bit": 10.0,
    "min_cpu_ram_gb": 8.0,
    "image_url": (
        "https://raw.githubusercontent.com/Sai-Vidyut/SatQuery-AI/main/"
        "experiments/phase9b_geochat/assets/sentinel2_smoketest.png"
    ),
    "image_sha256": "f330e6526a97bc3880bae5e75f45209bc98381042bb5ff0680d8fe3baa87f81b",
    "image_metadata": {
        "source": "COPERNICUS/S2_SR_HARMONIZED (Google Earth Engine)",
        "scene_id": "S2A_MSIL2A_20230815T095031_N0509_R079_T33UXP_20230815T155057",
        "acquisition_time_iso": "2023-08-15T09:57:24.627000+00:00",
        "bands": ["B4 (Red)", "B3 (Green)", "B2 (Blue)"],
        "scaling": "surface reflectance DN, stretched [0, 3000] -> [0, 255]",
        "aoi_wgs84": [
            16.546090477803443,
            48.164067553000365,
            16.65390952219656,
            48.23593244699964,
        ],
        "output_dimensions_px": 504,
        "label": "REAL_SENTINEL2_SMOKETEST",
    },
    "question": (
        "Describe the main land-cover types and objects visible in this satellite image."
    ),
    "prompt_system": (
        "A chat between a curious user and an artificial intelligence assistant. "
        "The assistant gives helpful, detailed, and polite answers to the user's questions."
    ),
    "checkpoint_bytes_fp16_verified": 14_126_079_376,
    "primary_load_strategy": "geochat_upstream_8bit_device_map_auto",
}

config_path = WORK_DIR / "smoke_config.json"
config_path.write_text(json.dumps(SMOKE_CONFIG, indent=2))

cpu_before = cpu_ram_snapshot()
print("Python:", platform.python_version())
print("Platform:", platform.platform())
print("torch (pre-install):", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print(
    "CPU RAM:",
    f"{cpu_before['used_gb']:.1f} GB used / {cpu_before['total_gb']:.1f} GB total",
    f"({cpu_before['available_gb']:.1f} GB available)",
)

if not torch.cuda.is_available():
    raise RuntimeError("CUDA not available. Set Runtime -> Change runtime type -> T4 GPU.")

props = torch.cuda.get_device_properties(0)
total_vram_gb = props.total_memory / (1024**3)
free_vram_gb = (props.total_memory - torch.cuda.memory_allocated(0)) / (1024**3)
print(f"GPU: {props.name}")
print(f"GPU VRAM: {total_vram_gb:.1f} GB total, {free_vram_gb:.1f} GB free (driver view)")

if cpu_before["available_gb"] < SMOKE_CONFIG["min_cpu_ram_gb"]:
    raise RuntimeError(
        f"Only {cpu_before['available_gb']:.1f} GB CPU RAM available; "
        f"need >= {SMOKE_CONFIG['min_cpu_ram_gb']:.0f} GB for safe loading."
    )

print("\n--- nvidia-smi ---")
subprocess.run(["nvidia-smi"], check=False)
print(f"\nConfig written to {config_path}")
