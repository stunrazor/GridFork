"""Tests for open-weight runner status (fully mocked, no network).

No test here starts a runner, downloads weights, or touches the network:
HTTP is stubbed and runner URLs are controlled via monkeypatch.
"""

import os

import httpx
import pytest

import openweights_client
from main import north_sea_storm_openweights, north_sea_storm_openweights_ask
from orchestrator import run_demo


def _ok_listing(ids):
    return httpx.Response(
        200,
        json={"data": [{"id": model_id} for model_id in ids]},
        request=httpx.Request("GET", "http://localhost:30000/v1/models"),
    )


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        openweights_client.runner_status("nope")


def test_unconfigured_runner_reports_setup_required_without_network(monkeypatch):
    monkeypatch.delenv("SPARK_OPEN_BASE_URL", raising=False)
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)

    def fail_get(*args, **kwargs):
        raise AssertionError("must not call network without a configured runner")

    monkeypatch.setattr(openweights_client.httpx, "get", fail_get)
    for key in ("spark-open", "glimmer"):
        status = openweights_client.runner_status(key)
        assert status["source"] == "setup-required"
        assert status["reachable"] is False
        assert status["served_models"] == []
        assert "dev.meta.ai" in status["docs"]


def test_setup_state_names_repo_and_serve_hint():
    os.environ.pop("SPARK_OPEN_BASE_URL", None)
    os.environ.pop("GLIMMER_BASE_URL", None)
    spark = openweights_client.runner_status("spark-open")
    assert spark["repo"] == "meta-models/Muse-Spark-Open-816B-A42B-NVFP4"
    assert "vllm serve" in spark["serve_hint"]
    assert "Blackwell" in spark["hardware"]
    glimmer = openweights_client.runner_status("glimmer")
    assert glimmer["repo"] == "meta-models/Muse-Glimmer-30B"
    assert "ollama run muse-glimmer" in glimmer["serve_hint"]
    assert "72 GB VRAM" in glimmer["hardware"]


def test_configured_runner_lists_served_models(monkeypatch):
    monkeypatch.setenv("SPARK_OPEN_BASE_URL", "http://localhost:30000/v1")
    # Hermetic without a key: a leaked provider key would switch the client
    # onto the headers path this local-runner double does not model.
    monkeypatch.delenv("SPARK_OPEN_API_KEY", raising=False)
    captured = {}

    def fake_get(url, timeout=None):
        captured["url"] = url
        return _ok_listing(["meta-models/Muse-Spark-Open-816B-A42B-NVFP4"])

    monkeypatch.setattr(openweights_client.httpx, "get", fake_get)
    status = openweights_client.runner_status("spark-open")
    assert status["source"] == "openweights-local"
    assert status["reachable"] is True
    assert captured["url"] == "http://localhost:30000/v1/models"
    assert status["served_models"] == ["meta-models/Muse-Spark-Open-816B-A42B-NVFP4"]


def test_models_listing_sends_provider_key_when_set(monkeypatch):
    monkeypatch.setenv("SPARK_OPEN_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("SPARK_OPEN_API_KEY", "provider-key")
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["headers"] = headers
        return _ok_listing(["meta-models/Muse-Spark-Open-816B-A42B"])

    monkeypatch.setattr(openweights_client.httpx, "get", fake_get)
    status = openweights_client.runner_status("spark-open")
    assert status["reachable"] is True
    assert captured["headers"] == {
        "Authorization": "Bearer " + os.environ["SPARK_OPEN_API_KEY"]
    }


def test_dead_runner_reports_unreachable(monkeypatch):
    monkeypatch.setenv("GLIMMER_BASE_URL", "http://localhost:11434/v1")

    def error_get(*args, **kwargs):
        raise httpx.ConnectError("nothing listening")

    monkeypatch.setattr(openweights_client.httpx, "get", error_get)
    status = openweights_client.runner_status("glimmer")
    assert status["source"] == "unreachable"
    assert status["reachable"] is False


def test_status_endpoint_defaults_and_passes_model(monkeypatch):
    monkeypatch.delenv("SPARK_OPEN_BASE_URL", raising=False)
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)
    assert north_sea_storm_openweights()["model"] == "spark-open"
    assert north_sea_storm_openweights()["source"] == "setup-required"
    assert north_sea_storm_openweights("glimmer")["model"] == "glimmer"


def _ok_completion(text):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions"),
    )


def test_severity_prompt_is_deterministic_and_grounded():
    findings = run_demo()["findings"]
    first = openweights_client.build_severity_prompt(findings)
    assert first == openweights_client.build_severity_prompt(findings)
    assert "sea: disrupted" in first
    assert "LOW, MODERATE, HIGH," in first


def test_serve_as_defaults_and_override(monkeypatch):
    monkeypatch.delenv("GLIMMER_MODEL_NAME", raising=False)
    assert openweights_client._serve_as("glimmer") == "muse-glimmer"
    monkeypatch.setenv("GLIMMER_MODEL_NAME", "custom-name")
    assert openweights_client._serve_as("glimmer") == "custom-name"


def test_generate_reports_setup_required_without_runner(monkeypatch):
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without a configured runner")

    monkeypatch.setattr(openweights_client.httpx, "post", fail_post)
    result = openweights_client.generate_text("glimmer", "prompt")
    assert result["source"] == "setup-required"
    assert result["text"] is None


def test_generate_rejects_unknown_model():
    with pytest.raises(ValueError):
        openweights_client.generate_text("nope", "prompt")


def test_generate_posts_openai_shape_without_key_by_default(monkeypatch):
    monkeypatch.setenv("GLIMMER_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.delenv("GLIMMER_API_KEY", raising=False)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _ok_completion("HIGH: sea leg blocked.")

    monkeypatch.setattr(openweights_client.httpx, "post", fake_post)
    result = openweights_client.generate_text("glimmer", "prompt")
    assert result == {
        "model": "glimmer",
        "source": "openweights-local",
        "text": "HIGH: sea leg blocked.",
    }
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["json"]["model"] == "muse-glimmer"
    assert captured["json"]["messages"] == [{"role": "user", "content": "prompt"}]
    assert "Authorization" not in captured["headers"]


def test_generate_sends_provider_key_when_set(monkeypatch):
    monkeypatch.setenv("SPARK_OPEN_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("SPARK_OPEN_API_KEY", "provider-key")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return _ok_completion("MODERATE: reroutes available.")

    monkeypatch.setattr(openweights_client.httpx, "post", fake_post)
    result = openweights_client.generate_text("spark-open", "prompt")
    assert result["source"] == "openweights-local"
    assert captured["headers"]["Authorization"] == "Bearer provider-key"
    assert "provider-key" not in str(result)


def test_generate_reports_unreachable_on_error(monkeypatch):
    monkeypatch.setenv("GLIMMER_BASE_URL", "http://localhost:11434/v1")

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("nothing listening")

    monkeypatch.setattr(openweights_client.httpx, "post", error_post)
    result = openweights_client.generate_text("glimmer", "prompt")
    assert result["source"] == "unreachable"
    assert result["text"] is None


def test_ask_endpoint_uses_mocked_runner(monkeypatch):
    monkeypatch.setenv("GLIMMER_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(
        openweights_client.httpx, "post", lambda *a, **k: _ok_completion("HIGH.")
    )
    body = north_sea_storm_openweights_ask("glimmer")
    assert body["openweights"]["source"] == "openweights-local"
    assert body["openweights"]["text"] == "HIGH."
    assert body["ranked_options"][0]["option_id"] == "rail-reroute"


def test_ask_endpoint_setup_required_without_runner(monkeypatch):
    monkeypatch.delenv("SPARK_OPEN_BASE_URL", raising=False)
    body = north_sea_storm_openweights_ask()
    assert body["openweights"]["model"] == "spark-open"
    assert body["openweights"]["source"] == "setup-required"
