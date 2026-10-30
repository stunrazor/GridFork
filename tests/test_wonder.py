"""Tests for the Muse Wonder cascade brief (fully mocked, no network).

No test here requires a real API key or network access: HTTP is stubbed and
META_MODEL_API_KEY is controlled via monkeypatch with a fake value.
"""

import httpx

import wonder_client
from main import north_sea_storm_brief
from orchestrator import run_demo

FAKE_KEY = "test-key-not-real"


def _ranked():
    return run_demo()["ranked_options"]


def _findings():
    return run_demo()["findings"]


def _ok_response(text):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", wonder_client.CHAT_COMPLETIONS_URL),
    )


def test_prompt_builder_is_deterministic():
    first = wonder_client.build_brief_prompt(_ranked(), _findings())
    second = wonder_client.build_brief_prompt(_ranked(), _findings())
    assert first == second
    assert "rail-reroute" in first
    assert "sea: disrupted" in first


def test_deterministic_brief_has_all_four_labels():
    text = wonder_client.deterministic_brief(_ranked(), _findings())
    for label in ("IMPACTS:", "RECOMMENDED_REROUTE:", "TRADEOFFS:", "CONFIDENCE:"):
        assert label in text
    assert "rail-reroute" in text
    assert "sea disrupted" in text


def test_fetch_uses_documented_endpoint_model_and_format(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _ok_response("Wonder brief text")

    monkeypatch.setattr(wonder_client.httpx, "post", fake_post)
    assert wonder_client.fetch_wonder_brief("prompt", FAKE_KEY) == "Wonder brief text"
    assert captured["url"] == "https://api.meta.ai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "muse-wonder-1.0"
    assert captured["json"]["messages"] == [{"role": "user", "content": "prompt"}]


def test_generate_brief_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without a key")

    monkeypatch.setattr(wonder_client.httpx, "post", fail_post)
    brief = wonder_client.generate_brief(_ranked(), _findings())
    assert brief["source"] == "deterministic"
    assert "RECOMMENDED_REROUTE:" in brief["text"]


def test_generate_brief_falls_back_on_api_error(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(wonder_client.httpx, "post", error_post)
    brief = wonder_client.generate_brief(_ranked(), _findings())
    assert brief["source"] == "deterministic"


def test_generate_brief_uses_wonder_on_success(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        wonder_client.httpx, "post", lambda *a, **k: _ok_response("Live Wonder text")
    )
    brief = wonder_client.generate_brief(_ranked(), _findings())
    assert brief == {"source": "muse-wonder", "text": "Live Wonder text"}


def test_brief_endpoint_deterministic_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    body = north_sea_storm_brief()
    assert body["brief"]["source"] == "deterministic"
    assert [o["option_id"] for o in body["ranked_options"]] == [
        "rail-reroute", "road-reroute", "air-lift", "sea-wait",
    ]


def test_brief_endpoint_uses_mocked_wonder(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        wonder_client.httpx, "post", lambda *a, **k: _ok_response("Endpoint Wonder text")
    )
    body = north_sea_storm_brief()
    assert body["brief"] == {"source": "muse-wonder", "text": "Endpoint Wonder text"}
