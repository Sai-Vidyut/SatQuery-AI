# Cell 2 — install a clean, conflict-free inference environment (do NOT reinstall torch)
import importlib
import os
import subprocess
import sys

import torch

hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
if hf_token:
    os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
    print("HF_TOKEN detected in environment (value not printed).")

# Colab ships packages we do not need for this smoke test but which pin newer
# transformers/tokenizers/huggingface-hub and destabilize a transformers==4.36.2 stack.
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
    "pillow>=10.0.0",
    "huggingface_hub>=0.20.0,<1.0",
]

print("Installing pinned inference stack (torch untouched):", ", ".join(PINNED))
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *PINNED])

# bitsandbytes: detect Colab torch/CUDA and install a modern compatible build.
cuda_version = torch.version.cuda or "unknown"
torch_version = torch.__version__
print(f"Detected torch {torch_version}, CUDA {cuda_version}")

subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "bitsandbytes"], check=False)
if cuda_version.startswith("12."):
    bnb_spec = "bitsandbytes>=0.43.1"
elif cuda_version.startswith("11."):
    bnb_spec = "bitsandbytes>=0.41.1,<0.44"
else:
    bnb_spec = "bitsandbytes>=0.43.1"
print(f"Installing bitsandbytes for CUDA {cuda_version}: {bnb_spec}")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", bnb_spec])

print("\n--- python -m pip check ---")
subprocess.run([sys.executable, "-m", "pip", "check"], check=False)

print("\n--- torch CUDA probe ---")
subprocess.run(
    [
        sys.executable,
        "-c",
        "import torch; print('torch:', torch.__version__); "
        "print('cuda:', torch.version.cuda); "
        "print('cuda_available:', torch.cuda.is_available())",
    ],
    check=True,
)

print("\n--- bitsandbytes import probe ---")
subprocess.run(
    [
        sys.executable,
        "-c",
        "import bitsandbytes as bnb; print('bitsandbytes:', bnb.__version__)",
    ],
    check=True,
)

print("\n--- nvidia-smi ---")
subprocess.run(["nvidia-smi"], check=False)

importlib.invalidate_caches()

import accelerate
import bitsandbytes as bnb
import transformers


def verify_bitsandbytes_cuda() -> None:
    """Fail cleanly before model load if bitsandbytes cannot use CUDA."""
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available after dependency install. "
            "Set Runtime -> Change runtime type -> T4 GPU."
        )
    try:
        layer = bnb.nn.Linear8bitLt(32, 32, has_fp16_weights=False).to("cuda")
        x = torch.randn(1, 32, device="cuda", dtype=torch.float16)
        _ = layer(x)
        del layer, x
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
    except Exception as exc:
        raise RuntimeError(
            "bitsandbytes failed CUDA initialization. "
            f"torch={torch.__version__}, cuda={torch.version.cuda}, "
            f"bitsandbytes={bnb.__version__}. "
            "This smoke test requires working 8-bit CUDA kernels. "
            f"Underlying error: {exc}"
        ) from exc


verify_bitsandbytes_cuda()

check = subprocess.run(
    [sys.executable, "-m", "pip", "check"],
    capture_output=True,
    text=True,
)
if check.returncode != 0:
    output = (check.stdout or "") + (check.stderr or "")
    critical_markers = [
        "transformers",
        "tokenizers",
        "torch",
        "bitsandbytes",
        "accelerate",
        "sentencepiece",
    ]
    critical_lines = [
        line for line in output.splitlines() if any(m in line.lower() for m in critical_markers)
    ]
    if critical_lines:
        raise RuntimeError(
            "Unresolved dependency conflicts for the GeoChat inference stack:\n"
            + "\n".join(critical_lines)
        )
    print("pip check reported non-critical warnings:\n", output)

print("\nInstalled versions:")
print("  torch:", torch.__version__, "(Colab CUDA build — not reinstalled)")
print("  transformers:", transformers.__version__)
print("  accelerate:", accelerate.__version__)
print("  bitsandbytes:", bnb.__version__)
print("  CUDA runtime:", torch.version.cuda)
print("bitsandbytes CUDA verification: PASSED")
print("Dependency environment OK.")
