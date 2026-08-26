#!/usr/bin/env bash
# Colab T4 launcher for the standalone GeoChat inference service (Phase 16 validation).
# Uses the EXISTING services/geochat FastAPI app — no backend, no mock engine.
#
# Run from the SatQuery-AI repository root:
#   cd /content/SatQuery-AI
#   bash services/geochat/scripts/colab_start.sh
#
# Health check (second Colab cell while server is running):
#   curl http://127.0.0.1:8000/health
#
# Colab reserves port 8080 for its Node process — default bind is 8000 here only.
# Override: export GEOCHAT_PORT=8000  (or GEOCHAT_SERVICE_PORT)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# --- Requirement 1: must be run from SatQuery-AI repository root ---
if [[ ! -f "${REPO_ROOT}/services/geochat/geochat_service/main.py" ]]; then
  echo "ERROR: Cannot locate services/geochat/geochat_service/main.py from script path." >&2
  echo "       Expected SatQuery-AI layout at: ${REPO_ROOT}" >&2
  exit 1
fi

if [[ "$(pwd -P)" != "$(cd "${REPO_ROOT}" && pwd -P)" ]]; then
  echo "ERROR: Run this script from the SatQuery-AI repository root." >&2
  echo "" >&2
  echo "  cd ${REPO_ROOT}" >&2
  echo "  bash services/geochat/scripts/colab_start.sh" >&2
  exit 1
fi

GEOCHAT_REPO="${GEOCHAT_REPO:-https://github.com/mbzuai-oryx/GeoChat.git}"
GEOCHAT_SRC="${GEOCHAT_SRC:-/content/geochat}"
GEOCHAT_MODEL_ID="${GEOCHAT_MODEL_ID:-MBZUAI/geochat-7B}"
GEOCHAT_SERVICE_HOST="${GEOCHAT_SERVICE_HOST:-0.0.0.0}"
# Colab default 8000 (8080 is used by Colab's Node). GEOCHAT_PORT is a Colab-friendly alias.
GEOCHAT_SERVICE_PORT="${GEOCHAT_PORT:-${GEOCHAT_SERVICE_PORT:-8000}}"
GEOCHAT_EAGER_LOAD="${GEOCHAT_EAGER_LOAD:-true}"

echo "============================================================"
echo " SatQuery GeoChat service — Colab T4 validation launcher"
echo "============================================================"
echo "Repository:   ${REPO_ROOT}"
echo "Service root: ${SERVICE_ROOT}"
echo "GeoChat src:  ${GEOCHAT_SRC}"
echo "Model:        ${GEOCHAT_MODEL_ID}"
echo "Listen:       ${GEOCHAT_SERVICE_HOST}:${GEOCHAT_SERVICE_PORT}"
echo "Eager load:   ${GEOCHAT_EAGER_LOAD} (weights download on service start)"
echo "Endpoints:    GET /health  POST /v1/vqa  POST /v1/caption"
echo ""

# Requirement 10: never use fake/development inference engine.
unset GEOCHAT_SERVICE_FAKE_ENGINE

# Requirement 6: HF auth from environment only.
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

echo "--- Startup diagnostics ---"
python3 - <<'PY'
import platform
import sys

print(f"python:         {platform.python_version()}")

try:
    import torch
except ImportError as exc:
    print("ERROR: torch is not available. Use Colab Runtime -> Change runtime type -> T4 GPU.", file=sys.stderr)
    raise SystemExit(1) from exc

print(f"torch:          {torch.__version__}")
print(f"cuda runtime:   {torch.version.cuda}")
print(f"cuda available: {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    print("ERROR: CUDA GPU is unavailable. Select a T4 GPU runtime before running this launcher.", file=sys.stderr)
    raise SystemExit(1)
idx = torch.cuda.current_device()
print(f"gpu name:       {torch.cuda.get_device_name(idx)}")
PY

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi || true
else
  echo "nvidia-smi: not found (continuing)"
fi
echo ""

echo "--- GeoChat upstream source (architecture only; no model weights yet) ---"
if [[ -d "${GEOCHAT_SRC}/geochat" ]]; then
  echo "GeoChat source already present at ${GEOCHAT_SRC}"
else
  echo "Cloning ${GEOCHAT_REPO} -> ${GEOCHAT_SRC}"
  git clone --depth 1 "${GEOCHAT_REPO}" "${GEOCHAT_SRC}"
fi
export GEOCHAT_SRC
echo ""

echo "--- Verify Phase 9B GeoChat patches before service start ---"
export SERVICE_ROOT
python3 - <<'PY'
import os
import sys
from pathlib import Path

service_root = Path(os.environ["SERVICE_ROOT"])
sys.path.insert(0, str(service_root))
from geochat_service.patches import apply_geochat_patches, verify_geochat_patches

root = Path(os.environ["GEOCHAT_SRC"])
apply_geochat_patches(root)
verify_geochat_patches(root)
print(f"[geochat] Phase 9B patches applied and verified at {root}")
PY
echo ""

echo "--- Install services/geochat dependencies (Colab torch untouched) ---"
export SERVICE_ROOT REPO_ROOT
python3 - <<'PY'
import os
import subprocess
import sys

import torch

hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
if hf_token:
    os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

# Remove Colab packages that pin incompatible transformers stacks.
REMOVE_PACKAGES = ["sentence-transformers", "gradio", "gradio_client"]
subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", *REMOVE_PACKAGES], check=False)

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
print("Installing pinned inference stack (torch not reinstalled):", ", ".join(PINNED))
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
print(f"Installing GeoChat service package: {service_root}")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-e", service_root])

import bitsandbytes as bnb

if not torch.cuda.is_available():
    raise SystemExit("ERROR: CUDA unavailable after dependency install.")

layer = bnb.nn.Linear8bitLt(32, 32, has_fp16_weights=False).to("cuda")
x = torch.randn(1, 32, device="cuda", dtype=torch.float16)
_ = layer(x)
del layer, x
torch.cuda.synchronize()
torch.cuda.empty_cache()
print("bitsandbytes CUDA verification: PASSED")
PY
echo ""

echo "--- Phase 9B loading strategy (geochat_service.inference.GeoChatInferenceEngine) ---"
echo "  model:            ${GEOCHAT_MODEL_ID}"
echo "  load_in_8bit:     True"
echo "  device_map:       auto"
echo "  low_cpu_mem_usage: True"
echo "  clip_interpolate: deferred 336px -> 504px after checkpoint load"
echo "  load_strategy:    geochat_upstream_8bit_device_map_auto_deferred_clip504"
echo "  image API:        base64 bytes only (no filesystem paths exposed)"
echo ""

echo "--- Service summary ---"
echo "Provider:       geochat_service (real inference engine)"
echo "Fake engine:    disabled"
echo "SatQuery backend: NOT started"
echo "Listening:      ${GEOCHAT_SERVICE_HOST}:${GEOCHAT_SERVICE_PORT}"
echo ""
echo "Local health check (run in another Colab cell while this cell stays alive):"
echo "  curl http://127.0.0.1:${GEOCHAT_SERVICE_PORT}/health"
echo ""
if [[ "${1:-}" == "--setup-only" ]]; then
  echo "Setup complete (--setup-only; uvicorn not started)."
  exit 0
fi

echo "Starting uvicorn via Python supervisor (captures exit code + logs)..."
echo "============================================================"

export GEOCHAT_MODEL_ID
export GEOCHAT_EAGER_LOAD
export GEOCHAT_SERVICE_HOST
export GEOCHAT_SERVICE_PORT

# Foreground supervisor keeps Colab cell alive and records exit status.
exec python3 "${SCRIPT_DIR}/colab_supervisor.py" \
  --skip-setup \
  --host "${GEOCHAT_SERVICE_HOST}" \
  --port "${GEOCHAT_SERVICE_PORT}"
