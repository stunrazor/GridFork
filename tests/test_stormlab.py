"""Tests for the Storm Scenario Lab page and the offline challenge mock.

No test here requires a real API key, a runner, or network access: HTTP is
stubbed, credentials are removed via monkeypatch, and the mock path never
calls the network by construction.
"""

from grid_page import render_grid_page
from main import north_sea_storm_challenge, north_sea_storm_lab
from orchestrator import run_challenge, run_demo
from storm_lab import render_storm_lab


def _lab():
    return render_storm_lab()


def test_lab_is_deterministic():
    assert _lab() == _lab()


def test_lab_has_typed_input_run_button_and_push_to_talk():
    html = _lab()
    assert "Storm Scenario Lab" in html
    assert "lab-input" in html
    assert "Run scenario" in html
    assert "lab-talk" in html
    assert "Hold to talk" in html
    assert "Insert mock question" in html


def test_lab_runs_everything_on_demand_only():
    html = _lab()
    script = html.split("<script>", 1)[1]
    for path in (
        "/demo/north-sea-storm/whatif?q=",
        "/demo/north-sea-storm/transcribe",
        "/demo/north-sea-storm/challenge?models=",
        "/demo/north-sea-storm/image",
    ):
        assert script.count(path) == 1
    # Microphone is touched only inside the push-to-talk handler.
    assert script.count("getUserMedia") == 1


def test_lab_labels_advisory_illustrative_and_synthetic():
    html = _lab()
    lowered = html.lower()
    assert "advisory" in lowered
    assert "illustrative" in lowered
    assert "synthetic" in lowered
    assert "sam" in lowered


def test_lab_avoids_banned_framing_words():
    html = _lab().lower()
    for word in ("dashboard", "command center", "control tower"):
        assert word not in html


def test_lab_endpoint_returns_lab_html():
    html = north_sea_storm_lab()
    assert "Storm Scenario Lab" in html
    assert "Run scenario" in html


def test_grid_page_links_to_storm_lab():
    assert 'href="/demo/storm-lab"' in render_grid_page()


def test_challenge_mock_uses_no_network_and_labels_mock(monkeypatch):
    monkeypatch.delenv("SPARK_OPEN_BASE_URL", raising=False)
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("mock challenge must not call the network")

    import openweights_client

    monkeypatch.setattr(openweights_client.httpx, "post", fail_post)
    body = run_challenge(["spark-open", "glimmer"], mock=True)
    assert body["synthetic"] is True
    assert [c["deterministic_top"] for c in body["cases"]] == [
        "rail-reroute",
        "rail-reroute",
        "road-reroute",
    ]
    assert len(body["results"]) == 6
    for entry in body["results"]:
        assert entry["source"] == "mock"
        assert entry["advisory"] is True
        assert entry["schema_valid"] is True
        assert entry["latency_ms"] is None
        assert entry["usage"] is None
    for summary in body["summary"]:
        assert summary["schema_valid"] == 3
        assert summary["agreements"] == 2
        assert summary["agreement_rate"] == round(2 / 3, 4)
        assert summary["total_tokens"] is None


def test_challenge_mock_endpoint_shape_and_unknown_model(monkeypatch):
    monkeypatch.delenv("SPARK_OPEN_BASE_URL", raising=False)
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)
    body = north_sea_storm_challenge(models="glimmer", mock=True)
    assert [s["model"] for s in body["summary"]] == ["glimmer"]
    assert len(body["results"]) == 3
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        north_sea_storm_challenge(models="nope", mock=True)
    assert exc_info.value.status_code == 400


def test_baseline_ranking_unchanged_when_new_features_unused(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("SPARK_OPEN_BASE_URL", raising=False)
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)
    # Exercise the new paths without credentials or runners attached.
    run_challenge(["spark-open", "glimmer"], mock=True)
    run_challenge(["spark-open", "glimmer"])
    demo = run_demo()
    assert [o["option_id"] for o in demo["ranked_options"]] == [
        "rail-reroute",
        "road-reroute",
        "air-lift",
        "sea-wait",
    ]
    assert demo["ranked_options"][0]["score"] == 0.7988
