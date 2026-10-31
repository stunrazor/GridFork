"""Tests for the Wonder-powered what-if planner (fully mocked, no network).

No test here requires a real API key or network access: HTTP is stubbed and
META_MODEL_API_KEY is controlled via monkeypatch with a fake value.
"""

import httpx
import pytest
from fastapi import HTTPException

import wonder_client
from grid_page import render_grid_page
from main import north_sea_storm_whatif
from orchestrator import (
    apply_whatif_assumptions,
    load_scenario,
    run_demo,
    run_whatif,
)

FAKE_KEY = "test-key-not-real"
EXAMPLE_Q = "What if Rotterdam closes for six more hours?"


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


def test_deterministic_parses_rotterdam_six_hours():
    parsed = wonder_client.deterministic_whatif(EXAMPLE_Q)
    assert [(a["mode"], a["field"], a["delta"]) for a in parsed["assumptions"]] == [
        ("sea", "delay_hours", 6)
    ]
    assert parsed["assumptions"][0]["reason"]
    assert "sea" in parsed["explanation"]
    assert "6" in parsed["explanation"]


def test_deterministic_parses_digits_and_negation():
    parsed = wonder_client.deterministic_whatif("What if rail clears 10 hours early?")
    assert [(a["mode"], a["field"], a["delta"]) for a in parsed["assumptions"]] == [
        ("rail", "delay_hours", -10)
    ]


def test_deterministic_parses_truck_cost():
    parsed = wonder_client.deterministic_whatif("What if the truck reroute costs $500 more?")
    assert [(a["mode"], a["field"], a["delta"]) for a in parsed["assumptions"]] == [
        ("road", "cost_usd", 500)
    ]


def test_deterministic_unknown_question_yields_no_assumptions():
    parsed = wonder_client.deterministic_whatif("What if everything is fine?")
    assert parsed["assumptions"] == []
    assert "unchanged" in parsed["explanation"]


def test_deterministic_parser_is_deterministic():
    assert wonder_client.deterministic_whatif(EXAMPLE_Q) == wonder_client.deterministic_whatif(
        EXAMPLE_Q
    )


def test_whatif_prompt_is_deterministic_and_mentions_question():
    first = wonder_client.build_whatif_prompt(EXAMPLE_Q, _ranked(), _findings())
    second = wonder_client.build_whatif_prompt(EXAMPLE_Q, _ranked(), _findings())
    assert first == second
    assert EXAMPLE_Q in first
    assert "JSON" in first
    assert "rail-reroute" in first


def test_parse_whatif_response_valid_json_with_fence():
    text = (
        '```json\n{"assumptions": [{"mode": "sea", "field": "delay_hours", '
        '"delta": 6, "reason": "port closure extended"}], '
        '"explanation": "Sea leg waits six hours longer."}\n```'
    )
    parsed = wonder_client.parse_whatif_response(text)
    assert parsed["assumptions"] == [
        {
            "mode": "sea",
            "field": "delay_hours",
            "delta": 6,
            "reason": "port closure extended",
        }
    ]
    assert parsed["explanation"] == "Sea leg waits six hours longer."


def test_parse_whatif_response_rejects_bad_json():
    with pytest.raises(ValueError):
        wonder_client.parse_whatif_response("not json at all")


def test_parse_whatif_response_drops_invalid_items():
    text = (
        '{"assumptions": [{"mode": "sea", "field": "delay_hours", "delta": 6}, '
        '{"mode": "hyperloop", "field": "delay_hours", "delta": 2}, '
        '{"mode": "air", "field": "teleport", "delta": 1}], "explanation": "Sea slips."}'
    )
    parsed = wonder_client.parse_whatif_response(text)
    assert [(a["mode"], a["field"], a["delta"]) for a in parsed["assumptions"]] == [
        ("sea", "delay_hours", 6)
    ]


def test_generate_whatif_offline_uses_no_network(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without a key")

    monkeypatch.setattr(wonder_client.httpx, "post", fail_post)
    result = wonder_client.generate_whatif(EXAMPLE_Q, _ranked(), _findings())
    assert result["source"] == "deterministic"
    assert [(a["mode"], a["field"], a["delta"]) for a in result["assumptions"]] == [
        ("sea", "delay_hours", 6)
    ]
    assert result["explanation"]


def test_generate_whatif_uses_wonder_on_success(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    body = (
        '{"assumptions": [{"mode": "sea", "field": "delay_hours", "delta": 6}], '
        '"explanation": "Live Wonder explanation."}'
    )
    monkeypatch.setattr(
        wonder_client.httpx, "post", lambda *a, **k: _ok_response(body)
    )
    result = wonder_client.generate_whatif(EXAMPLE_Q, _ranked(), _findings())
    assert result["source"] == "muse-wonder"
    assert result["explanation"] == "Live Wonder explanation."
    assert [(a["mode"], a["field"], a["delta"]) for a in result["assumptions"]] == [
        ("sea", "delay_hours", 6)
    ]


def test_generate_whatif_falls_back_on_bad_json(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        wonder_client.httpx, "post", lambda *a, **k: _ok_response("not json")
    )
    result = wonder_client.generate_whatif(EXAMPLE_Q, _ranked(), _findings())
    assert result["source"] == "deterministic"
    assert [(a["mode"], a["field"], a["delta"]) for a in result["assumptions"]] == [
        ("sea", "delay_hours", 6)
    ]


def test_apply_assumptions_updates_only_where_asked():
    scenario = apply_whatif_assumptions(
        load_scenario(),
        [{"mode": "sea", "field": "delay_hours", "delta": 6, "reason": "test"}],
    )
    assert scenario["modes"]["sea"]["delay_hours"] == 54
    assert scenario["modes"]["rail"]["delay_hours"] == 6
    # The loaded baseline on disk is untouched by the copy.
    assert load_scenario()["modes"]["sea"]["delay_hours"] == 48


def test_apply_assumptions_clamps_at_zero():
    scenario = apply_whatif_assumptions(
        load_scenario(),
        [{"mode": "rail", "field": "delay_hours", "delta": -100, "reason": "test"}],
    )
    assert scenario["modes"]["rail"]["delay_hours"] == 0


def test_run_whatif_recomputes_with_engine(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    result = run_whatif(EXAMPLE_Q)
    assert result["question"] == EXAMPLE_Q
    assert result["synthetic"] is True
    assert result["whatif"]["source"] == "deterministic"
    # Baseline is the untouched deterministic ranking.
    assert [o["option_id"] for o in result["ranked_baseline"]] == [
        "rail-reroute",
        "road-reroute",
        "air-lift",
        "sea-wait",
    ]
    # The engine — not the model — recomputed the after state: sea slipped 6h.
    sea_after = next(
        o for o in result["ranked_options"] if o["option_id"] == "sea-wait"
    )
    sea_before = next(
        o for o in result["ranked_baseline"] if o["option_id"] == "sea-wait"
    )
    assert sea_after["time_saved_hours"] == -6
    assert sea_after["score"] == sea_before["score"]  # still min time, max cost score
    # The widened time range lifts the middle options, proving a full rescore.
    road_after = next(
        o for o in result["ranked_options"] if o["option_id"] == "road-reroute"
    )
    road_before = next(
        o for o in result["ranked_baseline"] if o["option_id"] == "road-reroute"
    )
    assert road_after["score"] > road_before["score"]
    # Before/after comparison covers every option.
    assert [c["option_id"] for c in result["comparison"]] == [
        o["option_id"] for o in result["ranked_options"]
    ]
    for entry in result["comparison"]:
        assert {"option_id", "score_before", "score_after", "rank_before", "rank_after"} <= set(
            entry
        )
    assert result == run_whatif(EXAMPLE_Q)


def test_run_whatif_rejects_blank():
    with pytest.raises(ValueError):
        run_whatif("   ")


def test_endpoint_function_returns_before_after_shape(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    body = north_sea_storm_whatif(q=EXAMPLE_Q)
    assert body["question"] == EXAMPLE_Q
    assert body["whatif"]["source"] == "deterministic"
    assert len(body["ranked_baseline"]) == 4
    assert len(body["ranked_options"]) == 4
    assert len(body["comparison"]) == 4
    assert len(body["findings_after"]) == 4


def test_endpoint_function_rejects_blank_with_400():
    with pytest.raises(HTTPException) as exc_info:
        north_sea_storm_whatif(q="  ")
    assert exc_info.value.status_code == 400


def test_grid_page_has_whatif_planner():
    html = render_grid_page()
    assert "What-if planner" in html
    assert "whatif-input" in html
    assert "Run what-if" in html
    assert "/demo/north-sea-storm/whatif?q=" in html
    script = html.split("<script>", 1)[1]
    assert script.count("/demo/north-sea-storm/whatif?q=") == 1
