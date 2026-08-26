# Cell 8 — write smoke_test_result.json and print pass/fail summary
import json
import platform
from pathlib import Path

import psutil
import torch

config = json.loads(Path("/content/phase9b_geochat_smoke/smoke_config.json").read_text())
diagnostic = json.loads(Path(config["diagnostic_path"]).read_text())
load_report = json.loads(Path(config["load_report_path"]).read_text())
inference_report = json.loads(
    Path("/content/phase9b_geochat_smoke/inference_report.json").read_text()
)

vm = psutil.virtual_memory()
result = {
    "phase": config["phase"],
    "artifact": "colab_geochat_smoke_test",
    "status": "PASSED",
    "model": config["model_id"],
    "fabricated": False,
    "python_version": platform.python_version(),
    "torch_version": diagnostic["torch_version"],
    "transformers_version": diagnostic["transformers_version"],
    "cuda_version": diagnostic["cuda_version"],
    "cuda_available": torch.cuda.is_available(),
    "load_strategy": load_report["load_strategy"],
    "image_metadata": config["image_metadata"],
    "image_path": config["image_path"],
    "pre_load_diagnostic_path": config["diagnostic_path"],
    "checkpoint_inspected": diagnostic["checkpoint"],
    "memory_budget_estimates": diagnostic["memory_budget_estimates"],
    "fit_assessment": diagnostic["fit_assessment"],
    "model_loaded": load_report["model_loaded"],
    "gpu_used": load_report["gpu_used"],
    "cpu_ram_before_load": diagnostic["cpu_ram_before_load"],
    "cpu_ram_after_load": load_report["cpu_ram_after_load"],
    "gpu_vram_before_load": diagnostic["gpu_vram_before_load"],
    "gpu_vram_after_load": load_report["gpu_vram_after_load"],
    "vram_before_load_gb": diagnostic["gpu_vram_before_load"]["allocated_gb"],
    "vram_after_load_gb": load_report["gpu_vram_after_load"]["allocated_gb"],
    "peak_vram_gb_after_load": load_report["peak_vram_gb_after_load"],
    "model_load_time_s": load_report["model_load_time_s"],
    "inference": inference_report,
    "peak_vram_gb_after_inference": inference_report["peak_vram_gb_after_inference"],
    "cpu_ram_at_result_gb": {
        "available": round(vm.available / (1024**3), 2),
        "used": round(vm.used / (1024**3), 2),
    },
}

result_path = Path(config["result_path"])
result_path.write_text(json.dumps(result, indent=2))

print("=" * 60)
print("SMOKE TEST PASSED")
print("=" * 60)
print("Load strategy:", result["load_strategy"])
print("Model loaded:", result["model_loaded"])
print("GPU used:", result["gpu_used"])
print("VRAM before load (GB):", result["vram_before_load_gb"])
print("VRAM after load (GB):", result["vram_after_load_gb"])
print("Peak VRAM after load (GB):", result["peak_vram_gb_after_load"])
print("Inference runtime (s):", result["inference"]["generation_time_s"])
print("Actual model response:")
print(result["inference"]["answer"])
print("Result JSON:", result_path)
