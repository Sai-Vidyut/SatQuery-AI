"""GeoChat service unit tests (no GPU required)."""

from __future__ import annotations

import base64
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GEOCHAT_SERVICE_FAKE_ENGINE", "true")

from geochat_service.main import app  # noqa: E402
from tests.fixtures import make_image_bytes, make_metadata


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "geochat_service"
    assert body["model_name"] == "MBZUAI/geochat-7B"
    assert body["model_loaded"] is True
    assert body["service_version"]


def test_valid_vqa_request(client):
    payload = {
        "model_id": "MBZUAI/geochat-7B",
        "question": "Describe the main land-cover types visible in this satellite image.",
        "image": make_image_bytes(),
        "image_metadata": make_metadata(),
        "parameters": {"max_new_tokens": 200, "temperature": 1.0, "do_sample": False},
    }
    res = client.post("/v1/vqa", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "geochat_service"
    assert body["model_name"] == "MBZUAI/geochat-7B"
    assert body["confidence_available"] is False
    assert body["answer"]


def test_malformed_request(client):
    res = client.post("/v1/vqa", json={"question": "only question"})
    assert res.status_code == 422


def test_missing_image(client):
    res = client.post(
        "/v1/vqa",
        json={
            "question": "What is visible?",
            "image_metadata": make_metadata(),
        },
    )
    assert res.status_code == 422


def test_missing_question(client):
    res = client.post(
        "/v1/vqa",
        json={
            "image": make_image_bytes(),
            "image_metadata": make_metadata(),
        },
    )
    assert res.status_code == 422


def test_caption_endpoint(client):
    res = client.post(
        "/v1/caption",
        json={
            "user_request": "Describe this satellite scene.",
            "image": make_image_bytes(),
            "image_metadata": make_metadata(),
            "mode": "scene_description",
        },
    )
    assert res.status_code == 200
    assert res.json()["description"]
