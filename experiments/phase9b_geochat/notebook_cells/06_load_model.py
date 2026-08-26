# Cell 6 — pre-load diagnostics, memory budget, then GeoChat upstream 8-bit load
import gc
import json
import platform
import sys
import threading
import time
from pathlib import Path

import bitsandbytes as bnb
import psutil
import torch
from huggingface_hub import HfApi, get_hf_file_metadata
from transformers import AutoTokenizer

config = json.loads(Path("/content/phase9b_geochat_smoke/smoke_config.json").read_text())
sys.path.insert(0, config["geochat_src"])

from geochat.model.language_model.geochat_llama import GeoChatLlamaForCausalLM

import transformers

model_id = config["model_id"]
WORK_DIR = Path(config["work_dir"])
VERIFIED_CHECKPOINT_BYTES = int(config["checkpoint_bytes_fp16_verified"])

# GeoChat upstream 8-bit kwargs — geochat/model/builder.py::load_pretrained_model()
#   kwargs = {"device_map": device_map}
#   if load_8bit: kwargs["load_in_8bit"] = True
#   GeoChatLlamaForCausalLM.from_pretrained(path, low_cpu_mem_usage=True, **kwargs)
# Cell 5 defers CLIP 336->504 interpolation so checkpoint 577-token weights load cleanly.
# Do NOT pass transformers' ignore_mismatched_sizes flag here — it skips position_embedding
# and leaves meta tensors when low_cpu_mem_usage=True, causing:
#   ValueError: weight is on the meta device, we need a `value` to put in on 0.
LOAD_KWARGS = {
    "device_map": "auto",
    "load_in_8bit": True,
    "low_cpu_mem_usage": True,
}
LOAD_STRATEGY = "geochat_upstream_8bit_device_map_auto_deferred_clip504"


def ram_gb() -> dict:
    vm = psutil.virtual_memory()
    return {
        "total_gb": round(vm.total / (1024**3), 2),
        "available_gb": round(vm.available / (1024**3), 2),
        "used_gb": round(vm.used / (1024**3), 2),
        "percent": vm.percent,
    }


def vram_gb() -> dict:
    if not torch.cuda.is_available():
        return {"available": False}
    idx = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(idx)
    total = props.total_memory
    allocated = torch.cuda.memory_allocated(idx)
    reserved = torch.cuda.memory_reserved(idx)
    return {
        "device_index": idx,
        "device_name": props.name,
        "total_gb": round(total / (1024**3), 2),
        "allocated_gb": round(allocated / (1024**3), 2),
        "reserved_gb": round(reserved / (1024**3), 2),
        "free_gb": round((total - reserved) / (1024**3), 2),
    }


def inspect_checkpoint_metadata() -> dict:
    api = HfApi()
    info = api.model_info(model_id)
    details = []
    total_bytes = 0
    for sibling in info.siblings or []:
        name = sibling.rfilename
        if not name.endswith((".bin", ".safetensors")):
            continue
        size = sibling.size
        source = "model_info.siblings.size"
        if not size:
            try:
                from huggingface_hub import hf_hub_url

                url = hf_hub_url(model_id, name, repo_type="model")
                size = get_hf_file_metadata(url).size
                source = "get_hf_file_metadata(url)"
            except Exception:
                size = 0
        if size:
            total_bytes += size
            details.append({"file": name, "bytes": size, "gb": round(size / (1024**3), 3), "source": source})
    if total_bytes == 0:
        total_bytes = VERIFIED_CHECKPOINT_BYTES
        details = [
            {
                "file": "(verified_total_phase9a)",
                "bytes": VERIFIED_CHECKPOINT_BYTES,
                "gb": round(VERIFIED_CHECKPOINT_BYTES / (1024**3), 3),
                "source": "checkpoint_bytes_fp16_verified",
            }
        ]
    return {
        "weight_file_count": len(details),
        "total_bytes": total_bytes,
        "total_gb_fp16_on_disk": round(total_bytes / (1024**3), 3),
        "files": details,
    }


def summarize_hf_device_map(hf_device_map: dict | None) -> dict:
    if not hf_device_map:
        return {"cuda:0": 0, "cpu": 0, "disk": 0}
    counts = {"cuda:0": 0, "cpu": 0, "disk": 0}
    for device in hf_device_map.values():
        if device in (0, "cuda", "cuda:0"):
            key = "cuda:0"
        elif device == "cpu":
            key = "cpu"
        elif device == "disk":
            key = "disk"
        else:
            key = str(device)
        counts[key] = counts.get(key, 0) + 1
    return counts


def finalize_vision_tower_for_504(vision_tower) -> dict:
    """Load checkpoint CLIP-336 weights, then apply GeoChat's 504px interpolation."""
    pe = vision_tower.vision_tower.vision_model.embeddings.position_embedding.weight
    if getattr(pe, "is_meta", False):
        raise RuntimeError(
            "vision_tower position_embedding is still on meta device after checkpoint load. "
            "Ensure cell 5 applied the clip_encoder defer-interpolation patch."
        )
    n_pos = int(pe.shape[0])
    if n_pos == 577:
        print(
            "Applying GeoChat CLIP position-embedding interpolation: "
            "336px (577 tokens) -> 504px (1297 tokens)..."
        )
        vision_tower.clip_interpolate_embeddings(image_size=504, patch_size=14)
        action = "interpolated_577_to_1297"
    elif n_pos == 1297:
        print("Vision tower already at 504px resolution (1297 position tokens).")
        action = "already_1297"
    else:
        raise RuntimeError(f"Unexpected position_embedding rows: {n_pos} (expected 577 or 1297)")
    vision_tower.is_loaded = True
    n_pos_after = int(
        vision_tower.vision_tower.vision_model.embeddings.position_embedding.weight.shape[0]
    )
    return {"position_tokens_before": n_pos, "position_tokens_after": n_pos_after, "action": action}


diag = {
    "python_version": platform.python_version(),
    "torch_version": torch.__version__,
    "transformers_version": transformers.__version__,
    "bitsandbytes_version": bnb.__version__,
    "cuda_version": torch.version.cuda,
    "gpu_name": torch.cuda.get_device_name(0),
    "cpu_ram_before_load": ram_gb(),
    "gpu_vram_before_load": vram_gb(),
    "load_strategy": LOAD_STRATEGY,
    "load_kwargs": LOAD_KWARGS,
    "vision_tower_note": (
        "Cell 5 defers clip_interpolate_embeddings until after checkpoint load. "
        "504x504 smoke image is GeoChat-native (see mm_utils.py / MODEL_ZOO.md)."
    ),
}
print("=== PRE-LOAD DIAGNOSTICS ===")
for k in (
    "python_version",
    "torch_version",
    "transformers_version",
    "bitsandbytes_version",
    "cuda_version",
    "gpu_name",
    "load_strategy",
):
    print(f"{k}: {diag[k]}")
print("load_kwargs:", LOAD_KWARGS)
print("CPU RAM:", diag["cpu_ram_before_load"])
print("GPU VRAM:", diag["gpu_vram_before_load"])

print("\nInspecting GeoChat checkpoint file sizes on Hugging Face...")
checkpoint = inspect_checkpoint_metadata()
diag["checkpoint"] = checkpoint
print(
    f"Checkpoint weight files: {checkpoint['weight_file_count']}, "
    f"total {checkpoint['total_gb_fp16_on_disk']:.3f} GB on disk (fp16 tensors)"
)
for entry in checkpoint["files"]:
    print(f"  - {entry['file']}: {entry['gb']:.3f} GB ({entry['source']})")

checkpoint_bytes = checkpoint["total_bytes"]
llm_fp16_gb = (checkpoint_bytes / (1024**3)) * 0.88
vision_fp16_gb = 1.7
projector_gb = 0.03
llm_8bit_gb = llm_fp16_gb * 0.52
gpu_free = diag["gpu_vram_before_load"]["free_gb"]
cpu_avail = diag["cpu_ram_before_load"]["available_gb"]

budget = {
    "estimated_fp16_memory_requirement_gb": round(
        llm_fp16_gb + vision_fp16_gb + projector_gb + 1.5, 2
    ),
    "estimated_8bit_memory_requirement_gb": round(
        llm_8bit_gb + vision_fp16_gb + projector_gb + 1.0, 2
    ),
    "fp16_cpu_materialize_ram_gb_est": round(checkpoint_bytes / (1024**3) + 2.0, 2),
    "notes": (
        "Uses GeoChat upstream builder.py 8-bit path: load_in_8bit=True + device_map='auto' "
        "+ low_cpu_mem_usage=True. CLIP 504 interpolation runs after checkpoint load."
    ),
}
diag["memory_budget_estimates"] = budget
print("\nMemory budget estimates:")
for k, v in budget.items():
    if k != "notes":
        print(f"  {k}: {v}")
print("  note:", budget["notes"])

diag["fit_assessment"] = {
    "int8_upstream_path_free_vram": gpu_free >= budget["estimated_8bit_memory_requirement_gb"],
    "fp16_single_gpu_total_vram": diag["gpu_vram_before_load"]["total_gb"]
    >= budget["estimated_fp16_memory_requirement_gb"],
    "fp16_cpu_materialize_colab_ram": cpu_avail >= budget["fp16_cpu_materialize_ram_gb_est"],
}
print("\nFit assessment (free VRAM = {:.2f} GB):".format(gpu_free))
for k, v in diag["fit_assessment"].items():
    print(f"  {k}: {v}")

Path(config["diagnostic_path"]).write_text(json.dumps(diag, indent=2))
print(f"\nWrote pre-load diagnostic: {config['diagnostic_path']}")

if not diag["fit_assessment"]["int8_upstream_path_free_vram"]:
    raise RuntimeError(
        f"Insufficient free VRAM for GeoChat upstream 8-bit load: {gpu_free:.2f} GB free, "
        f"estimated need {budget['estimated_8bit_memory_requirement_gb']:.2f} GB"
    )

gc.collect()
torch.cuda.empty_cache()

print("\nLoading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=False)

print(f"\nLoading GeoChat with strategy: {LOAD_STRATEGY}")
print("  (matches geochat/model/builder.py load_8bit=True path + deferred CLIP504 patch)")
for k, v in LOAD_KWARGS.items():
    print(f"  {k}={v!r}")

t0 = time.time()
load_error = None
model = None
memory_samples = []
vision_tower_report = None
stop_monitor = threading.Event()


def _memory_monitor() -> None:
    while not stop_monitor.is_set():
        sample = {
            "elapsed_s": round(time.time() - t0, 2),
            "cpu_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "gpu_allocated_gb": round(torch.cuda.memory_allocated() / (1024**3), 3),
            "gpu_reserved_gb": round(torch.cuda.memory_reserved() / (1024**3), 3),
        }
        memory_samples.append(sample)
        print(
            "[load-monitor]",
            f"t={sample['elapsed_s']}s",
            f"cpu_avail={sample['cpu_available_gb']}GB",
            f"gpu_alloc={sample['gpu_allocated_gb']}GB",
            f"gpu_reserved={sample['gpu_reserved_gb']}GB",
        )
        stop_monitor.wait(2.0)


monitor_thread = threading.Thread(target=_memory_monitor, daemon=True)
monitor_thread.start()

try:
    print("\n>>> CHECKPOINT: about to call GeoChatLlamaForCausalLM.from_pretrained(...)")
    model = GeoChatLlamaForCausalLM.from_pretrained(model_id, **LOAD_KWARGS)
    print(">>> CHECKPOINT: GeoChatLlamaForCausalLM.from_pretrained(...) returned successfully")

    hf_device_map = getattr(model, "hf_device_map", None)
    map_summary = summarize_hf_device_map(hf_device_map)
    print("Resolved hf_device_map module counts:", map_summary)
    if hf_device_map:
        print("Resolved hf_device_map (first 10 entries):")
        for i, (name, dev) in enumerate(hf_device_map.items()):
            if i >= 10:
                print(f"  ... ({len(hf_device_map) - 10} more)")
                break
            print(f"  {name}: {dev}")

    # Do NOT call vision_tower.load_model() here — it reloads openai/clip-vit-large-patch14-336
    # from scratch and discards checkpoint vision weights. Apply GeoChat's intended
    # clip_interpolate_embeddings() after the 577-token checkpoint weights are loaded.
    vision_tower = model.get_vision_tower()
    vision_tower_report = finalize_vision_tower_for_504(vision_tower)
    vision_tower.to(device="cuda", dtype=torch.float16)
    image_processor = vision_tower.image_processor
    model.eval()
    print(">>> CHECKPOINT: vision tower on cuda, model.eval() complete")
except Exception as exc:
    load_error = repr(exc)
    raise RuntimeError(f"GeoChat 8-bit load failed: {exc}") from exc
finally:
    stop_monitor.set()
    monitor_thread.join(timeout=3.0)
    hf_device_map = getattr(model, "hf_device_map", None) if model is not None else None
    load_report = {
        "load_strategy": LOAD_STRATEGY,
        "load_kwargs": LOAD_KWARGS,
        "vision_tower_finalize": vision_tower_report,
        "hf_device_map_summary": summarize_hf_device_map(hf_device_map),
        "model_loaded": model is not None,
        "load_error": load_error,
        "model_load_time_s": round(time.time() - t0, 2),
        "memory_samples_during_load": memory_samples,
        "cpu_ram_after_load": ram_gb(),
        "gpu_vram_after_load": vram_gb(),
        "peak_vram_gb_after_load": round(torch.cuda.max_memory_allocated() / (1024**3), 3),
        "gpu_used": torch.cuda.get_device_name(0),
    }
    Path(config["load_report_path"]).write_text(json.dumps(load_report, indent=2))
    print(f"Wrote load report: {config['load_report_path']}")

if model is None:
    raise RuntimeError("Model load failed — see load_report.json")

print(f"Model loaded in {load_report['model_load_time_s']:.1f}s")
print("hf_device_map summary:", load_report["hf_device_map_summary"])
print("vision_tower_finalize:", load_report["vision_tower_finalize"])
print("CPU RAM after load:", load_report["cpu_ram_after_load"])
print("GPU VRAM after load:", load_report["gpu_vram_after_load"])
