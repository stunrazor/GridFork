"""Tests for the first Muse Spark integration (fully mocked, no network).

No test here requires a real API key or network access: HTTP is stubbed and
META_MODEL_API_KEY is controlled via monkeypatch with a fake value.
"""

import httpx

import spark_client
from main import north_sea_storm_summary
from orchestrator import run_demo

FAKE_KEY = "test-key-not-real"


def _ranked():
    return run_demo()["ranked_options"]


def _ok_response(text):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", spark_client.CHAT_COMPLETIONS_URL),
    )


def test_prompt_builder_is_deterministic():
    ranked = _ranked()
    first, second = spark_client.build_summary_prompt(ranked), spark_client.build_summary_prompt(ranked)
    assert first == second
    assert "rail-reroute" in first


def test_deterministic_summary_names_top_option():
    text = spark_client.deterministic_summary(_ranked())
    assert "rail-reroute" in text


def test_fetch_uses_documented_endpoint_model_and_format(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _ok_response("Spark summary text")

    monkeypatch.setattr(spark_client.httpx, "post", fake_post)
    assert spark_client.fetch_spark_summary("prompt", FAKE_KEY) == "Spark summary text"
    assert captured["url"] == "https://api.meta.ai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "muse-spark-1.3"
    assert captured["json"]["messages"] == [{"role": "user", "content": "prompt"}]


def test_generate_summary_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without a key")

    monkeypatch.setattr(spark_client.httpx, "post", fail_post)
    summary = spark_client.generate_summary(_ranked())
    assert summary["source"] == "deterministic"
    assert "rail-reroute" in summary["text"]


def test_generate_summary_falls_back_on_api_error(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(spark_client.httpx, "post", error_post)
    summary = spark_client.generate_summary(_ranked())
    assert summary["source"] == "deterministic"


def test_generate_summary_uses_spark_on_success(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        spark_client.httpx, "post", lambda *a, **k: _ok_response("Live Spark text")
    )
    summary = spark_client.generate_summary(_ranked())
    assert summary == {"source": "muse-spark", "text": "Live Spark text"}


def test_summary_endpoint_deterministic_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    body = north_sea_storm_summary()
    assert body["summary"]["source"] == "deterministic"
    assert [o["option_id"] for o in body["ranked_options"]] == [
        "rail-reroute", "road-reroute", "air-lift", "sea-wait",
    ]


def test_summary_endpoint_uses_mocked_spark(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        spark_client.httpx, "post", lambda *a, **k: _ok_response("Endpoint Spark text")
    )
    body = north_sea_storm_summary()
    assert body["summary"] == {"source": "muse-spark", "text": "Endpoint Spark text"}
