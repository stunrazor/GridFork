"""Tests for the Muse Image illustration (fully mocked, no network).

No test here requires a real API key or network access: HTTP is stubbed and
META_MODEL_API_KEY is controlled via monkeypatch with a fake value.
"""

import httpx

import image_client
from main import north_sea_storm_image

FAKE_KEY = "test-key-not-real"
FAKE_B64 = "UklGRfake-bytes"


def _ok_response():
    return httpx.Response(
        200,
        json={"data": [{"b64_json": FAKE_B64}]},
        request=httpx.Request("POST", image_client.IMAGES_URL),
    )


def test_prompt_builder_is_deterministic_and_grounded():
    first = image_client.build_scenario_prompt("LABEL", 8.5, 110)
    second = image_client.build_scenario_prompt("LABEL", 8.5, 110)
    assert first == second
    assert "8.5" in first
    assert "110" in first
    assert "LABEL" in first


def test_fetch_uses_documented_endpoint_model_and_format(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _ok_response()

    monkeypatch.setattr(image_client.httpx, "post", fake_post)
    result = image_client.fetch_generated_image("prompt", FAKE_KEY)
    assert result == {"output_format": "webp", "b64_json": FAKE_B64}
    assert captured["url"] == "https://api.meta.ai/v1/images/generations"
    assert captured["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "muse-image-1.0"
    assert captured["json"]["prompt"] == "prompt"
    assert captured["json"]["n"] == 1


def test_generate_reports_unavailable_without_key_and_no_bytes(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without a key")

    monkeypatch.setattr(image_client.httpx, "post", fail_post)
    result = image_client.generate_scenario_image("LABEL", 8.5, 110)
    assert result["source"] == "unavailable"
    assert result["data_url"] is None
    assert "META_MODEL_API_KEY" in result["note"]


def test_generate_reports_unavailable_on_api_error(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(image_client.httpx, "post", error_post)
    result = image_client.generate_scenario_image("LABEL", 8.5, 110)
    assert result["source"] == "unavailable"
    assert result["data_url"] is None


def test_generate_returns_data_url_on_success(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        image_client.httpx, "post", lambda *a, **k: _ok_response()
    )
    result = image_client.generate_scenario_image("LABEL", 8.5, 110)
    assert result["source"] == "muse-image"
    assert result["data_url"] == f"data:image/webp;base64,{FAKE_B64}"
    assert "not a photograph" in result["note"]


def test_image_endpoint_deterministic_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    body = north_sea_storm_image()
    assert body["image"]["source"] == "unavailable"
    assert body["image"]["data_url"] is None
    assert [o["option_id"] for o in body["ranked_options"]] == [
        "rail-reroute", "road-reroute", "air-lift", "sea-wait",
    ]


def test_image_endpoint_uses_mocked_image(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        image_client.httpx, "post", lambda *a, **k: _ok_response()
    )
    body = north_sea_storm_image()
    assert body["image"]["source"] == "muse-image"
    assert body["image"]["data_url"].startswith("data:image/webp;base64,")
