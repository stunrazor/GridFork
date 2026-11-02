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


def test_ask_snippet_renders_text_only():
    from ask_box import render_ask_box, render_ask_script

    snippet = render_ask_box("probe") + render_ask_script("probe")
    assert "innerHTML" not in snippet
    assert "textContent" in snippet
    for word in ("dashboard", "command center", "control tower", "console"):
        assert word not in snippet.lower()
