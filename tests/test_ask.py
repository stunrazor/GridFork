"""Tests for the Ask GridFork box (fully mocked, no network).

One shared snippet renders on the grid, routes, lab, and brief-card
pages; answers come from Muse Spark grounded in the deterministic
ranking, or report setup/unavailable without guessing.
"""

import os

import httpx
import pytest
from fastapi import HTTPException

import spark_client
from briefing_card import render_brief_card
from grid_page import render_grid_page
from main import north_sea_storm_ask
from orchestrator import run_ask, run_demo
from routes_page import render_routes_page
from storm_lab import render_storm_lab

EXAMPLE_Q = "Which option is cheapest and what does it trade off?"


def _spark_response(text):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", spark_client.CHAT_COMPLETIONS_URL),
    )


def test_ask_prompt_grounds_in_ranking_and_limits_scope():
    demo = run_demo()
    prompt = spark_client.build_ask_prompt(
        EXAMPLE_Q, demo["findings"], demo["ranked_options"]
    )
    assert EXAMPLE_Q in prompt
    for option in demo["ranked_options"]:
        assert option["option_id"] in prompt
    for finding in demo["findings"]:
        assert finding["mode"] in prompt
    assert "Out of scope" in prompt


def _live_context():
    return {
        "provenance": {
            "sea": {"delay_hours": "estimated-from-conditions"},
            "air": {"delay_hours": "synthetic"},
            "road": {"delay_hours": "estimated-from-conditions"},
            "rail": {"delay_hours": "synthetic"},
        },
        "marine": {"source": "open-meteo", "live": True, "wave_height_m": 0.4},
        "wind": {"source": "open-meteo", "live": True, "wind_kph": 45.0},
        "air": {"source": "setup-required", "live": False},
        "road": {
            "source": "tomtom",
            "live": True,
            "worst_ratio": 0.9,
            "incidents": {"count": 2, "closures": 0},
            "route": {"transit_hours": 17.2},
        },
        "rail": {"source": "setup-required", "live": False},
    }


def test_ask_prompt_includes_live_conditions():
    demo = run_demo()
    prompt = spark_client.build_ask_prompt(
        EXAMPLE_Q, demo["findings"], demo["ranked_options"], live=_live_context()
    )
    assert "0.4" in prompt
    assert "45.0" in prompt
    assert "open-meteo" in prompt
    assert "tomtom" in prompt
    assert "estimated-from-conditions" in prompt


def test_run_ask_grounds_in_live_snapshot(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "unit-meta-key")
    for var in (
        "OPENSKY_CLIENT_ID",
        "OPENSKY_CLIENT_SECRET",
        "TOMTOM_API_KEY",
        "NS_API_KEY",
        "DB_CLIENT_ID",
        "DB_API_KEY",
        "ADSB_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        text = str(url)
        if "marine-api" in text:
            return httpx.Response(
                200,
                json={"current": {"time": "2026-11-01T19:15", "wave_height": 0.4}},
                request=httpx.Request("GET", text),
            )
        assert "api.open-meteo" in text
        return httpx.Response(
            200,
            json={"current": {"time": "2026-11-01T19:15", "wind_speed_10m": 12.5}},
            request=httpx.Request("GET", text),
        )

    def fake_post(url, headers=None, json=None, timeout=None):
        if "entur" in str(url):
            return httpx.Response(
                200,
                json={"data": {"stopPlace": {"estimatedCalls": []}}},
                request=httpx.Request("POST", str(url)),
            )
        captured["prompt"] = json["messages"][0]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Calm seas; sail."}}]},
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    body = run_ask(EXAMPLE_Q)
    assert body["answer"]["source"] == "muse-spark"
    assert "0.4" in captured["prompt"]
    assert "measured" in captured["prompt"]


def test_answer_question_reports_setup_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    demo = run_demo()
    answer = spark_client.answer_question(
        EXAMPLE_Q, demo["findings"], demo["ranked_options"]
    )
    assert answer["source"] == "setup-required"
    assert answer["text"] is None
    assert "META_MODEL_API_KEY" in answer["detail"]


def test_answer_question_reports_unavailable_on_failure(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "unit-meta-key")

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", error_post)
    demo = run_demo()
    answer = spark_client.answer_question(
        EXAMPLE_Q, demo["findings"], demo["ranked_options"]
    )
    assert answer["source"] == "unavailable"
    assert answer["text"] is None


def test_answer_question_returns_spark_text(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "unit-meta-key")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["auth"] = headers["Authorization"]
        captured["model"] = json["model"]
        assert EXAMPLE_Q in json["messages"][0]["content"]
        return _spark_response("Rail is cheapest; it trades 4h for $700.")

    monkeypatch.setattr(httpx, "post", fake_post)
    demo = run_demo()
    answer = spark_client.answer_question(
        EXAMPLE_Q, demo["findings"], demo["ranked_options"]
    )
    assert answer["source"] == "muse-spark"
    assert answer["text"] == "Rail is cheapest; it trades 4h for $700."
    assert captured["auth"] == "Bearer " + os.environ["META_MODEL_API_KEY"]
    assert captured["model"] == spark_client.MODEL_ID


def test_run_ask_rejects_blank_and_overlong():
    with pytest.raises(ValueError):
        run_ask("   ")
    with pytest.raises(ValueError):
        run_ask("x" * 501)


def test_run_ask_returns_question_and_answer(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    body = run_ask(EXAMPLE_Q)
    assert body["question"] == EXAMPLE_Q
    assert body["answer"]["source"] == "setup-required"


def test_endpoint_function_rejects_blank_with_400():
    with pytest.raises(HTTPException) as exc_info:
        north_sea_storm_ask(q="  ")
    assert exc_info.value.status_code == 400


def _assert_ask_box(html, prefix):
    assert "Ask GridFork" in html
    assert f"{prefix}-ask-input" in html
    assert f"{prefix}-ask-btn" in html
    assert f"{prefix}-ask-out" in html
    script = html.split("<script>", 1)[1]
    assert script.count("/demo/north-sea-storm/ask") == 1
    assert "textContent" in script


def test_grid_page_has_ask_box():
    _assert_ask_box(render_grid_page(), "grid")


def test_routes_page_has_ask_box():
    _assert_ask_box(render_routes_page(run_demo()), "rt")


def test_lab_page_has_ask_box():
    _assert_ask_box(render_storm_lab(), "lab")


def test_brief_card_has_ask_box():
    _assert_ask_box(render_brief_card(run_demo()), "brief")


def _mocked_models(monkeypatch, spark_text="Spark says.", wonder_text="Wonder says."):
    """Route mocked chat completions by model id; returns captured prompts."""
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        if "query" in (json or {}):
            return httpx.Response(
                200,
                json={"data": {"stopPlace": {"estimatedCalls": []}}},
                request=httpx.Request("POST", str(url)),
            )
        model = json["model"]
        captured.setdefault(model, []).append(json["messages"][0]["content"])
        text = wonder_text if model == "muse-wonder-1.0" else spark_text
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": text}}]},
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    return captured


def _offline_snapshot(monkeypatch):
    """Force the live snapshot fully offline (baseline values, no network)."""

    def error_http(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", error_http)


def test_ask_routes_scenario_questions_to_wonder(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "unit-meta-key")
    _offline_snapshot(monkeypatch)
    captured = _mocked_models(monkeypatch)
    for question in (
        "What if Rotterdam closes for six more hours?",
        "Suppose the storm stalls; what changes?",
        "Explain why rail is ranked first.",
    ):
        body = run_ask(question)
        assert body["routed_to"] == "wonder"
        assert body["answer"]["source"] == "muse-wonder"
    assert "What if Rotterdam closes" in captured["muse-wonder-1.0"][0]
    assert "rail-reroute" in captured["muse-wonder-1.0"][0]


def test_ask_routes_factual_questions_to_spark(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "unit-meta-key")
    _offline_snapshot(monkeypatch)
    captured = _mocked_models(monkeypatch)
    for question in (
        "Which option is cheapest?",
        "How bad is Hamburg road congestion right now?",
        "What is the sea delay?",
    ):
        body = run_ask(question)
        assert body["routed_to"] == "spark"
        assert body["answer"]["source"] == "muse-spark"
    assert any("How bad is Hamburg" in prompt for prompt in captured["muse-spark-1.3"])


def test_ask_routing_names_its_reason():
    from orchestrator import route_ask

    assert route_ask("What if winds rise?")[0] == "wonder"
    assert "what if" in route_ask("What if winds rise?")[1]
    assert route_ask("Which option is cheapest?")[0] == "spark"


def test_wonder_answer_reports_setup_and_unavailable(monkeypatch):
    import wonder_client

    demo = run_demo()
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    answer = wonder_client.answer_ask(EXAMPLE_Q, demo["findings"], demo["ranked_options"])
    assert answer["source"] == "setup-required"
    assert answer["text"] is None

    monkeypatch.setenv("META_MODEL_API_KEY", "unit-meta-key")

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", error_post)
    answer = wonder_client.answer_ask(EXAMPLE_Q, demo["findings"], demo["ranked_options"])
    assert answer["source"] == "unavailable"
    assert answer["text"] is None


def test_fastest_alternative_picks_minimum_total_time():
    from orchestrator import fastest_alternative

    snap = {
        "baseline": {"planned_sea_transit_hours": 24},
        "modes": {
            "sea": {"delay_hours": 48, "transit_hours": 24},
            "air": {"delay_hours": 4, "transit_hours": 6},
            "road": {"delay_hours": 6, "transit_hours": 17.2},
            "rail": {"delay_hours": 4, "transit_hours": 30},
        },
    }
    fastest = fastest_alternative(snap)
    assert fastest["mode"] == "air"
    assert fastest["option_id"] == "air-lift"
    assert fastest["total_hours"] == 10


def test_run_ask_reports_fastest_alternative(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "unit-meta-key")
    _offline_snapshot(monkeypatch)
    _mocked_models(monkeypatch)
    body = run_ask(EXAMPLE_Q)
    fastest = body["fastest_alternative"]
    assert fastest["mode"] == "air"
    assert fastest["option_id"] == "air-lift"
    assert fastest["total_hours"] == 10


def test_ask_box_shows_fastest_alternate_line():
    from ask_box import render_ask_script

    script = render_ask_script("probe")
    assert "fastest_alternative" in script
    assert "Fastest alternate" in script


def test_ask_box_sits_above_mode_content():
    grid = render_grid_page()
    assert grid.index("grid-ask-input") < grid.index("Specialist findings")
    routes = render_routes_page(run_demo())
    assert routes.index("rt-ask-input") < routes.index("Route comparison")
    lab = render_storm_lab()
    assert lab.index("lab-ask-input") < lab.index("1. Scenario question")
    card = render_brief_card(run_demo())
    assert card.index("brief-ask-input") < card.index("<h2>Impacts</h2>")


def test_ask_snippet_renders_text_only():
    from ask_box import render_ask_box, render_ask_script

    snippet = render_ask_box("probe") + render_ask_script("probe")
    assert "innerHTML" not in snippet
    assert "textContent" in snippet
    for word in ("dashboard", "command center", "control tower", "console"):
        assert word not in snippet.lower()
