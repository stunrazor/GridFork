"""Tests for open-weight runner status (fully mocked, no network).

No test here starts a runner, downloads weights, or touches the network:
HTTP is stubbed and runner URLs are controlled via monkeypatch.
"""

import os

import httpx
import pytest

import openweights_client
from main import north_sea_storm_openweights


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
