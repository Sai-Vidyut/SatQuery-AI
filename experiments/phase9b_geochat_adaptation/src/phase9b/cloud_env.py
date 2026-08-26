"""Cloud/GPU environment detection.

Pure inspection — never fabricates a GPU that isn't there. Safe to import
and call with no GPU present (returns a CloudEnvironmentReport describing
that CUDA is unavailable rather than raising or faking a result).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CloudEnvironmentReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cuda_available: bool
    torch_installed: bool
    torch_version: str | None = None
    device_count: int = 0
    device_names: list[str] = Field(default_factory=list)
    total_vram_bytes_per_device: list[int] = Field(default_factory=list)
    driver_or_import_error: str | None = None

    @property
    def total_vram_gb_pooled(self) -> float:
        return sum(self.total_vram_bytes_per_device) / (1024**3)

    def require_cuda(self) -> None:
        """Raise a clear, honest error if no GPU is available.

        Callers that need a real GPU (the smoke test) must call this
        instead of silently falling back to CPU or fabricating output.
        """
        if not self.torch_installed:
            raise RuntimeError(
                "torch is not installed in this environment. Install the "
                "'cloud' extra (see pyproject.toml) inside a GPU notebook "
                "session before running the smoke test."
            )
        if not self.cuda_available:
            raise RuntimeError(
                "CUDA is not available in this environment "
                f"(torch={self.torch_version}). The GeoChat smoke test "
                "requires a real GPU and will not run on CPU or fabricate "
                "a result. See README.md 'Cloud setup'."
            )


def detect_cloud_environment() -> CloudEnvironmentReport:
    """Inspect the current process for a usable CUDA GPU.

    Never raises for the "no GPU" case — that is a normal, expected result
    on the local Mac dev machine and in plain CI. Only import-time surprises
    are captured in `driver_or_import_error`.
    """
    try:
        import torch
    except ImportError as exc:
        return CloudEnvironmentReport(
            cuda_available=False,
            torch_installed=False,
            driver_or_import_error=f"{type(exc).__name__}: {exc}",
        )

    try:
        cuda_available = bool(torch.cuda.is_available())
    except Exception as exc:  # pragma: no cover - defensive, driver-dependent
        return CloudEnvironmentReport(
            cuda_available=False,
            torch_installed=True,
            torch_version=str(torch.__version__),
            driver_or_import_error=f"{type(exc).__name__}: {exc}",
        )

    if not cuda_available:
        return CloudEnvironmentReport(
            cuda_available=False,
            torch_installed=True,
            torch_version=str(torch.__version__),
        )

    device_count = torch.cuda.device_count()
    device_names = [torch.cuda.get_device_name(i) for i in range(device_count)]
    vram_bytes = [
        torch.cuda.get_device_properties(i).total_memory for i in range(device_count)
    ]
    return CloudEnvironmentReport(
        cuda_available=True,
        torch_installed=True,
        torch_version=str(torch.__version__),
        device_count=device_count,
        device_names=device_names,
        total_vram_bytes_per_device=vram_bytes,
    )
