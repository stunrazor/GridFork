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


def test_lab_centers_on_corridor_picker():
    html = _lab()
    assert "<h1>GridFork scenario lab</h1>" in html
    assert "Worldwide snapshot" in html
    assert "lab-corridor" in html
    assert "lab-snapshot-btn" in html
    assert "Run live snapshot" in html
    assert "lab-ask-input" in html
    for gone in (
        "lab-input",
        "Run scenario",
        "lab-talk",
        "Insert mock question",
        "lab-challenge",
        "lab-illustration",
    ):
        assert gone not in html


def test_lab_runs_snapshot_and_ask_only():
    html = _lab()
    script = html.split("<script>", 1)[1]
    assert script.count("/snapshot?corridor=") == 1
    assert script.count("/snapshot?from=") == 1
    for gone in (
        "/demo/north-sea-storm/challenge?models=",
        "/demo/north-sea-storm/image",
    ):
        assert gone not in script
    # One mic left: Ask dictation, touched only in its hold-to-talk handler.
    assert script.count("/demo/north-sea-storm/transcribe") == 1
    assert script.count("getUserMedia") == 1
    assert script.count("pointerdown") == 1


def test_lab_single_knob_whatif_form():
    html = _lab()
    assert "Change one assumption" in html
    for target in ("lab-mode", "lab-field", "lab-delta", "lab-whatif-btn",
                   "lab-whatif-out", "Compare before/after"):
        assert target in html
    script = html.split("<script>", 1)[1]
    assert "labWhatifQuestion" in script
    assert "labWhatifContext" in script
    assert script.count("/demo/north-sea-storm/whatif?q=") == 1
    assert "Observed top:" in script
    assert "Hypothetical:" in script
    assert "innerHTML" not in script


def test_lab_generated_questions_parse_offline():
    from wonder_client import deterministic_whatif

    delay = deterministic_whatif("What if sea has 12 more hours of delay?")
    assert delay["assumptions"] == [
        {"mode": "sea", "field": "delay_hours", "delta": 12,
         "reason": "Parsed '12 more hours'."}
    ]
    relief = deterministic_whatif("What if road saves 4 hours?")
    assert relief["assumptions"] == [
        {"mode": "road", "field": "delay_hours", "delta": -4,
         "reason": "Parsed '4 hours'."}
    ]
    cost = deterministic_whatif("What if air costs $2000 more?")
    assert cost["assumptions"] == [
        {"mode": "air", "field": "cost_usd", "delta": 2000,
         "reason": "Parsed '$2000'."}
    ]


def test_lab_knob_rescores_selected_corridor(monkeypatch):
    import snapshot as snapshot_mod
    from orchestrator import run_whatif
    from tests.test_worldwide import _patch_live_layers

    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    _patch_live_layers(monkeypatch)
    snap = snapshot_mod.snapshot_for_corridor("north-sea")
    body = run_whatif("What if sea has 12 more hours of delay?",
                      snapshot=snap)
    assert body["whatif"]["assumptions"][0]["mode"] == "sea"
    assert body["whatif"]["assumptions"][0]["delta"] == 12
    assert body["ranked_baseline"] == snap["ranked_options"]
    sea_after = next(f for f in body["findings_after"]
                     if f["mode"] == "sea")
    sea_before = next(f for f in snap["findings"] if f["mode"] == "sea")
    assert sea_after["delay_hours"] == sea_before["delay_hours"] + 12


def test_lab_labels_estimates_and_picker():
    html = _lab()
    lowered = html.lower()
    assert "estimates" in lowered
    assert "corridor" in lowered
    assert "provenance" in lowered


def test_lab_avoids_banned_framing_words():
    html = _lab().lower()
    for word in ("dashboard", "command center", "control tower"):
        assert word not in html


def test_lab_endpoint_returns_lab_html():
    html = north_sea_storm_lab()
    assert "<h1>GridFork scenario lab</h1>" in html
    assert "Run live snapshot" in html


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
