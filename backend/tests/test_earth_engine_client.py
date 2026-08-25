import builtins
from unittest.mock import MagicMock, patch

import pytest

from app.adapters.imagery.earth_engine.client import EarthEngineClient
from app.core.errors import SatQueryError


def test_ee_client_missing_package(monkeypatch):
    real_import = builtins.__import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ee":
            raise ImportError("No module named 'ee'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    with pytest.raises(SatQueryError) as exc:
        EarthEngineClient.initialize()
    assert exc.value.code == "earth_engine_unavailable"


def test_ee_client_init_failure():
    fake_ee = MagicMock()
    fake_ee.Initialize.side_effect = RuntimeError("bad credentials")

    with patch.dict("sys.modules", {"ee": fake_ee}):
        with pytest.raises(SatQueryError) as exc:
            EarthEngineClient.initialize()
        assert exc.value.code == "earth_engine_auth_failed"
