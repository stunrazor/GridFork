"""Tests for the North Sea storm end-to-end demo."""

from fastapi.testclient import TestClient

from main import app, north_sea_storm
from orchestrator import build_options, collect_findings, load_scenario, run_demo, score_options

EXPECTED_ORDER = ["rail-reroute", "road-reroute", "air-lift", "sea-wait"]
EXPECTED_SCORES = {
    "rail-reroute": 0.7988,
    "road-reroute": 0.714,
    "air-lift": 0.6125,
    "sea-wait": 0.5225,
}


def test_demo_is_deterministic():
    assert run_demo() == run_demo()


def test_ranking_order_and_scores():
    ranked = run_demo()["ranked_options"]
    assert [o["option_id"] for o in ranked] == EXPECTED_ORDER
    assert [o["rank"] for o in ranked] == [1, 2, 3, 4]
    for option in ranked:
        assert option["score"] == EXPECTED_SCORES[option["option_id"]]


def test_tiebreak_by_option_id():
    base = {"cost_usd": 1000, "time_saved_hours": 5, "on_time_probability": 0.5, "confidence": 0.5}
    options = [
        {"option_id": "b-option", **base},
        {"option_id": "a-option", **base},
    ]
    ranked = score_options(options)
    assert [o["option_id"] for o in ranked] == ["a-option", "b-option"]
    assert ranked[0]["score"] == ranked[1]["score"]


def test_findings_cover_all_modes_with_synthetic_label():
    findings = collect_findings(load_scenario())
    assert [f["mode"] for f in findings] == ["sea", "air", "road", "rail"]
    required = {
        "mode", "synthetic", "status", "summary", "delay_hours",
        "cost_usd", "on_time_probability", "confidence", "risks", "recommendation",
    }
    for finding in findings:
        assert finding["synthetic"] is True
        assert required <= set(finding)
    assert next(f for f in findings if f["mode"] == "sea")["status"] == "disrupted"


def test_options_use_all_four_ranking_inputs():
    scenario = load_scenario()
    findings = collect_findings(scenario)
    options = build_options(findings, scenario["baseline"]["storm_delay_hours_if_waiting"])
    for option in options:
        for key in ("cost_usd", "time_saved_hours", "on_time_probability", "confidence"):
            assert key in option


def test_endpoint_function_returns_demo_shape():
    body = north_sea_storm()
    assert body["synthetic"] is True
    assert len(body["findings"]) == 4
    assert [o["option_id"] for o in body["ranked_options"]] == EXPECTED_ORDER


def test_endpoint_serves_ranked_demo():
    client = TestClient(app)
    response = client.get("/demo/north-sea-storm")
    assert response.status_code == 200
    body = response.json()
    assert body["synthetic"] is True
    assert [o["option_id"] for o in body["ranked_options"]] == EXPECTED_ORDER
