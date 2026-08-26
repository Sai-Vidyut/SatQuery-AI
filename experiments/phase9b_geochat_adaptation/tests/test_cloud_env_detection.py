import pytest

from phase9b.cloud_env import detect_cloud_environment


def test_detect_cloud_environment_never_raises():
    # Must succeed on the local Mac (no CUDA) without raising or faking a GPU.
    report = detect_cloud_environment()
    assert report.torch_installed is True or report.torch_installed is False
    assert report.cuda_available is True or report.cuda_available is False


def test_require_cuda_raises_clearly_when_unavailable():
    report = detect_cloud_environment()
    if report.cuda_available:
        pytest.skip("This test only asserts behavior when CUDA is unavailable (e.g. local Mac).")
    with pytest.raises(RuntimeError, match="CUDA is not available|torch is not installed"):
        report.require_cuda()


def test_report_never_claims_devices_without_cuda():
    report = detect_cloud_environment()
    if not report.cuda_available:
        assert report.device_count == 0
        assert report.device_names == []
        assert report.total_vram_bytes_per_device == []
