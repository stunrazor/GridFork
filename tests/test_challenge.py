"""Tests for the open-weight route challenge (fully mocked, no network).

No test here starts a runner, downloads weights, or touches the network:
HTTP is stubbed and runner URLs are controlled via monkeypatch.
"""

import httpx
import pytest
from fastapi import HTTPException

import openweights_client
from grid_page import render_grid_page
from main import north_sea_storm_challenge
from orchestrator import CHALLENGE_CASES, run_challenge, run_demo

RAIL_CRITIQUE = (
    '{"agree_with_top_pick": true, '
    '"preferred_option_id": "rail-reroute", '
    '"concerns": ["Single-corridor congestion"], "confidence": 0.8}'
)
USAGE = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}


def _ok_metered(text, usage=USAGE):
    payload = {"choices": [{"message": {"content": text}}]}
    if usage is not None:
        payload["usage"] = usage
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("POST", "http://runner.example/v1/chat/completions"),
    )


def _prompt():
    demo = run_demo()
    return openweights_client.build_critique_prompt(
        "case label", demo["findings"], demo["ranked_options"]
    )


def test_critique_prompt_is_deterministic_and_states_schema():
    assert _prompt() == _prompt()
    assert "case label" in _prompt()
    assert "JSON" in _prompt()
    assert "agree_with_top_pick" in _prompt()
    assert "preferred_option_id" in _prompt()
    assert "rail-reroute" in _prompt()
    assert "advisory" in _prompt()


def test_parse_critique_valid_with_fence():
    parsed = openweights_client.parse_critique_response(
        "```json\n" + RAIL_CRITIQUE + "\n```",
        ["rail-reroute", "road-reroute", "air-lift", "sea-wait"],
    )
    assert parsed == {
        "agree_with_top_pick": True,
        "preferred_option_id": "rail-reroute",
        "concerns": ["Single-corridor congestion"],
        "confidence": 0.8,
    }


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"agree_with_top_pick": true}',
        '{"agree_with_top_pick": "yes", "preferred_option_id": "rail-reroute",'
        ' "concerns": [], "confidence": 0.5}',
        '{"agree_with_top_pick": true, "preferred_option_id": "hyperloop",'
        ' "concerns": [], "confidence": 0.5}',
        '{"agree_with_top_pick": true, "preferred_option_id": "rail-reroute",'
        ' "concerns": "none", "confidence": 0.5}',
        '{"agree_with_top_pick": true, "preferred_option_id": "rail-reroute",'
        ' "concerns": [], "confidence": 2.0}',
        '{"agree_with_top_pick": true, "preferred_option_id": "rail-reroute",'
        ' "concerns": [], "confidence": "high"}',
        '["agree_with_top_pick"]',
    ],
)
def test_parse_critique_rejects_schema_violations(text):
    with pytest.raises(ValueError):
        openweights_client.parse_critique_response(
            text, ["rail-reroute", "road-reroute", "air-lift", "sea-wait"]
        )


def test_complete_metered_setup_required_without_network(monkeypatch):
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without a configured runner")

    monkeypatch.setattr(openweights_client.httpx, "post", fail_post)
    result = openweights_client.complete_with_metrics("glimmer", "prompt")
    assert result["source"] == "setup-required"
    assert result["text"] is None
    assert result["latency_ms"] is None
    assert result["usage"] is None


def test_complete_metered_success_reports_latency_usage_and_shape(monkeypatch):
    monkeypatch.setenv("GLIMMER_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.delenv("GLIMMER_API_KEY", raising=False)
    ticks = iter([100.0, 100.25])
    monkeypatch.setattr(
        openweights_client.time, "perf_counter", lambda: next(ticks)
    )
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _ok_metered(RAIL_CRITIQUE)

    monkeypatch.setattr(openweights_client.httpx, "post", fake_post)
    result = openweights_client.complete_with_metrics("glimmer", "prompt")
    assert result["source"] == "openweights-local"
    assert result["text"] == RAIL_CRITIQUE
    assert result["latency_ms"] == 250.0
    assert result["usage"] == USAGE
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["json"]["model"] == "muse-glimmer"
    assert "Authorization" not in captured["headers"]


def test_complete_metered_usage_none_when_absent(monkeypatch):
    monkeypatch.setenv("GLIMMER_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(
        openweights_client.httpx,
        "post",
        lambda *a, **k: _ok_metered(RAIL_CRITIQUE, usage=None),
    )
    result = openweights_client.complete_with_metrics("glimmer", "prompt")
    assert result["source"] == "openweights-local"
    assert result["usage"] is None
    assert result["latency_ms"] is not None


def test_complete_metered_unreachable_on_error(monkeypatch):
    monkeypatch.setenv("GLIMMER_BASE_URL", "http://localhost:11434/v1")

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("nothing listening")

    monkeypatch.setattr(openweights_client.httpx, "post", error_post)
    result = openweights_client.complete_with_metrics("glimmer", "prompt")
    assert result["source"] == "unreachable"
    assert result["text"] is None
    assert result["usage"] is None
    assert result["latency_ms"] is not None


def test_complete_metered_rejects_unknown_model():
    with pytest.raises(ValueError):
        openweights_client.complete_with_metrics("nope", "prompt")


def test_challenge_cases_cover_baseline_and_two_whatifs():
    assert [c["case_id"] for c in CHALLENGE_CASES] == [
        "baseline",
        "rotterdam-plus-6h",
        "rail-plus-30h",
    ]
    assert CHALLENGE_CASES[0]["assumptions"] == []
    assert CHALLENGE_CASES[1]["assumptions"][0]["mode"] == "sea"
    assert CHALLENGE_CASES[2]["assumptions"][0]["mode"] == "rail"


def test_challenge_offline_keeps_authoritative_ranking_without_network(monkeypatch):
    monkeypatch.delenv("SPARK_OPEN_BASE_URL", raising=False)
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without configured runners")

    monkeypatch.setattr(openweights_client.httpx, "post", fail_post)
    body = run_challenge()
    assert body["synthetic"] is True
    assert "advisory" in body["authoritative"]
    # Deterministic tops are authoritative: rail, rail, then road after +30h.
    assert [c["deterministic_top"] for c in body["cases"]] == [
        "rail-reroute",
        "rail-reroute",
        "road-reroute",
    ]
    assert len(body["results"]) == 6
    for entry in body["results"]:
        assert entry["advisory"] is True
        assert entry["source"] == "setup-required"
        assert entry["schema_valid"] is False
        assert entry["agrees_with_ranking"] is None
        assert entry["error"]
    for summary in body["summary"]:
        assert summary["cases"] == 3
        assert summary["schema_valid"] == 0
        assert summary["agreement_rate"] is None
        assert summary["total_tokens"] is None


def test_challenge_mocked_models_reports_agreement_validity_and_tokens(monkeypatch):
    monkeypatch.setenv("SPARK_OPEN_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("GLIMMER_BASE_URL", "https://provider.example/v1")
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json["model"])
        if len(calls) == 2:
            return _ok_metered("not json")
        return _ok_metered(RAIL_CRITIQUE)

    monkeypatch.setattr(openweights_client.httpx, "post", fake_post)
    body = run_challenge()
    by_model = {s["model"]: s for s in body["summary"]}
    # Both models prefer rail: agree on baseline and +6h, miss the road flip.
    assert by_model["glimmer"]["schema_valid"] == 3
    assert by_model["glimmer"]["agreements"] == 2
    assert by_model["glimmer"]["agreement_rate"] == round(2 / 3, 4)
    # Spark's second call is invalid JSON: 2 valid, 1 agreement.
    assert by_model["spark-open"]["schema_valid"] == 2
    assert by_model["spark-open"]["agreements"] == 1
    assert by_model["spark-open"]["agreement_rate"] == 0.5
    assert by_model["glimmer"]["total_tokens"] == 360
    assert by_model["spark-open"]["total_tokens"] == 360
    for summary in body["summary"]:
        assert summary["avg_latency_ms"] is not None
    spark_bad = [
        r
        for r in body["results"]
        if r["model"] == "spark-open" and r["case_id"] == "rotterdam-plus-6h"
    ][0]
    assert spark_bad["schema_valid"] is False
    assert spark_bad["agrees_with_ranking"] is None
    assert "invalid" in spark_bad["error"]
    # The deterministic ranking itself never comes from a model.
    assert body["cases"][2]["ranked_options"][0]["option_id"] == "road-reroute"


def test_challenge_rejects_unknown_model():
    with pytest.raises(ValueError):
        run_challenge(["glimmer", "nope"])


def test_challenge_endpoint_filters_models_and_shapes_offline(monkeypatch):
    monkeypatch.delenv("SPARK_OPEN_BASE_URL", raising=False)
    monkeypatch.delenv("GLIMMER_BASE_URL", raising=False)
    body = north_sea_storm_challenge()
    assert [s["model"] for s in body["summary"]] == ["spark-open", "glimmer"]
    assert len(body["cases"]) == 3
    only = north_sea_storm_challenge("glimmer")
    assert [s["model"] for s in only["summary"]] == ["glimmer"]
    assert len(only["results"]) == 3


def test_challenge_endpoint_rejects_unknown_model_with_400():
    with pytest.raises(HTTPException) as exc_info:
        north_sea_storm_challenge("nope")
    assert exc_info.value.status_code == 400


def test_grid_page_has_route_challenge():
    html = render_grid_page()
    assert "Route challenge" in html
    assert "Run route challenge" in html
    assert "Advisory only" in html
    assert "/demo/north-sea-storm/challenge?models=" in html
    script = html.split("<script>", 1)[1]
    assert script.count("/demo/north-sea-storm/challenge?models=") == 1
