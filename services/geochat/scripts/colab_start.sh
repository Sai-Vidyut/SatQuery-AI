#!/usr/bin/env bash
# Colab T4 launcher for the standalone GeoChat inference service (validation only).
# Does NOT start the SatQuery backend. Does NOT use the development/fake engine.
#
# Usage (Colab cell):
#   !bash /content/SatQuery-AI/services/geochat/scripts/colab_start.sh
#
# Optional environment variables (set before running):
#   HF_TOKEN or HUGGINGFACE_HUB_TOKEN  — Hugging Face auth if required
#   GEOCHAT_SRC                        — GeoChat upstream clone path (default: /content/geochat)
#   GEOCHAT_MODEL_ID                   — default: MBZUAI/geochat-7B
#   GEOCHAT_EAGER_LOAD                 — default: true (weights load when uvicorn starts)
#   GEOCHAT_SERVICE_PORT               — default: 8080
#
# Health check (run in a second Colab cell while the server is running):
#   curl http://127.0.0.1:8080/health

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GEOCHAT_REPO="${GEOCHAT_REPO:-https://github.com/mbzuai-oryx/GeoChat.git}"
GEOCHAT_SRC="${GEOCHAT_SRC:-/content/geochat}"
GEOCHAT_MODEL_ID="${GEOCHAT_MODEL_ID:-MBZUAI/geochat-7B}"
GEOCHAT_SERVICE_HOST="${GEOCHAT_SERVICE_HOST:-0.0.0.0}"
GEOCHAT_SERVICE_PORT="${GEOCHAT_SERVICE_PORT:-8080}"
GEOCHAT_EAGER_LOAD="${GEOCHAT_EAGER_LOAD:-true}"

echo "============================================================"
echo " SatQuery GeoChat service — Colab T4 validation launcher"
echo "============================================================"
echo "Service root: ${SERVICE_ROOT}"
echo "GeoChat src:  ${GEOCHAT_SRC}"
echo "Model:        ${GEOCHAT_MODEL_ID}"
echo "Bind:         ${GEOCHAT_SERVICE_HOST}:${GEOCHAT_SERVICE_PORT}"
echo "Eager load:   ${GEOCHAT_EAGER_LOAD} (weights download on service start)"
echo ""

# Never use fake/development inference engine in Colab validation.
unset GEOCHAT_SERVICE_FAKE_ENGINE

# Hugging Face auth — environment only; never hard-code tokens.
if [[ -n "${HF_TOKEN:-}" ]]; then
  export HF_TOKEN
  export HUGGINGFACE_HUB_TOKEN="${HUGGINGFACE_HUB_TOKEN:-$HF_TOKEN}"
  echo "HF_TOKEN: set (value not printed)"
elif [[ -n "${HUGGINGFACE_HUB_TOKEN:-}" ]]; then
  export HUGGINGFACE_HUB_TOKEN
  echo "HUGGINGFACE_HUB_TOKEN: set (value not printed)"
else
  echo "HF_TOKEN: not set (public model download only)"
fi
echo ""

echo "--- GPU / CUDA probe ---"
python3 - <<'PY'
import sys

try:
    import torch
except ImportError as exc:
    print("ERROR: torch is not available. Use Colab Runtime -> Change runtime type -> T4 GPU.", file=sys.stderr)
    raise SystemExit(1) from exc

print(f"torch:          {torch.__version__}")
print(f"cuda runtime:   {torch.version.cuda}")
print(f"cuda available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    idx = torch.cuda.current_device()
    print(f"gpu device:     {torch.cuda.get_device_name(idx)}")
else:
    print("ERROR: CUDA is not available. Select a GPU runtime before running this launcher.", file=sys.stderr)
    raise SystemExit(1)
PY

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi || true
else
  echo "nvidia-smi: not found (continuing)"
fi
echo ""

echo "--- Install GeoChat upstream source (no model weights yet) ---"
if [[ -d "${GEOCHAT_SRC}/geochat" ]]; then
  echo "GeoChat source already present at ${GEOCHAT_SRC}"
else
  echo "Cloning ${GEOCHAT_REPO} -> ${GEOCHAT_SRC}"
  git clone --depth 1 "${GEOCHAT_REPO}" "${GEOCHAT_SRC}"
fi
export GEOCHAT_SRC
echo ""

echo "--- Install services/geochat dependencies (Phase 9B pinned stack) ---"
echo "Note: Colab torch is left untouched; only inference + service deps are installed."

export SERVICE_ROOT
python3 - <<'PY'
import os
import subprocess
import sys

import torch

hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
if hf_token:
    os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

REMOVE_PACKAGES = [
    "sentence-transformers",
    "gradio",
    "gradio_client",
]
print("Removing Colab packages not required for GeoChat inference:", REMOVE_PACKAGES)
subprocess.run(
    [sys.executable, "-m", "pip", "uninstall", "-y", *REMOVE_PACKAGES],
    check=False,
)

PINNED = [
    "transformers==4.36.2",
    "tokenizers==0.15.2",
    "accelerate==0.25.0",
    "sentencepiece==0.1.99",
    "einops==0.6.1",
    "einops-exts==0.0.4",
    "psutil>=5.9.0",
    "huggingface_hub>=0.20.0,<1.0",
]
print("Installing pinned inference stack:", ", ".join(PINNED))
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *PINNED])

cuda_version = torch.version.cuda or "unknown"
subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "bitsandbytes"], check=False)
if cuda_version.startswith("12."):
    bnb_spec = "bitsandbytes>=0.43.1"
elif cuda_version.startswith("11."):
    bnb_spec = "bitsandbytes>=0.41.1,<0.44"
else:
    bnb_spec = "bitsandbytes>=0.43.1"
print(f"Installing bitsandbytes for CUDA {cuda_version}: {bnb_spec}")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", bnb_spec])

service_root = os.environ["SERVICE_ROOT"]
print(f"Installing GeoChat service package from {service_root} (base deps only; no torch reinstall)")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-e", service_root])

import bitsandbytes as bnb

if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable after dependency install.")

layer = bnb.nn.Linear8bitLt(32, 32, has_fp16_weights=False).to("cuda")
x = torch.randn(1, 32, device="cuda", dtype=torch.float16)
_ = layer(x)
del layer, x
torch.cuda.synchronize()
torch.cuda.empty_cache()
print("bitsandbytes CUDA verification: PASSED")
PY
echo ""

echo "--- Loading strategy (implemented in geochat_service.inference) ---"
echo "  load_in_8bit=True"
echo "  device_map=auto"
echo "  low_cpu_mem_usage=True"
echo "  deferred CLIP 336->504 interpolation after checkpoint load"
echo "  load_strategy=geochat_upstream_8bit_device_map_auto_deferred_clip504"
echo ""

SERVICE_URL="http://127.0.0.1:${GEOCHAT_SERVICE_PORT}"
PUBLIC_URL="http://${GEOCHAT_SERVICE_HOST}:${GEOCHAT_SERVICE_PORT}"

echo "--- Startup summary ---"
echo "Provider:     geochat_service (real GeoChatInferenceEngine)"
echo "Fake engine:  disabled (GEOCHAT_SERVICE_FAKE_ENGINE unset)"
echo "Backend:      NOT started (GeoChat service only)"
echo "Service URL:  ${SERVICE_URL}  (local health check)"
echo "Bind address: ${PUBLIC_URL}"
echo ""
echo "Health check (run in another Colab cell while server is running):"
echo "  curl http://127.0.0.1:${GEOCHAT_SERVICE_PORT}/health"
echo ""
echo "SatQuery backend (run on your machine, not in Colab):"
echo "  export GEOCHAT_VQA_PROVIDER=geochat_service"
echo "  export GEOCHAT_SERVICE_URL=<colab-tunnel-or-public-url>"
echo ""
echo "Starting uvicorn — model weights will download now (first start may take several minutes)..."
echo "============================================================"

export GEOCHAT_MODEL_ID
export GEOCHAT_EAGER_LOAD
export GEOCHAT_SERVICE_HOST
export GEOCHAT_SERVICE_PORT
export PYTHONPATH="${GEOCHAT_SRC}:${SERVICE_ROOT}:${PYTHONPATH:-}"

exec python3 -m uvicorn geochat_service.main:app \
  --host "${GEOCHAT_SERVICE_HOST}" \
  --port "${GEOCHAT_SERVICE_PORT}" \
  --log-level info
