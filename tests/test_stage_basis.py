"""Tests for Ask-as-basis stage wiring: scenario exposure, corridor-aware
stages, endpoint params, and the Route Briefing stage context.

Every test is hermetic: live layers are rigged via the worldwide helper,
model clients are stubbed or keyless, and geo lookups never run.
"""

import pytest
from fastapi import HTTPException

import orchestrator
import routes_page
import sam_client
import snapshot as snapshot_mod
import wonder_client
from main import (
    north_sea_storm_challenge,
    north_sea_storm_image,
    north_sea_storm_summary,
    north_sea_storm_vision,
    north_sea_storm_whatif,
)
from tests.test_worldwide import _patch_live_layers


def _north_sea(monkeypatch):
    _patch_live_layers(monkeypatch)
    return snapshot_mod.snapshot_for_corridor("north-sea")


def _short_hop(monkeypatch):
    _patch_live_layers(monkeypatch)
    return snapshot_mod.build_snapshot(
        {"name": "Quezon City", "lat": 14.65, "lon": 121.05},
        {"name": "Baliuag", "lat": 14.95, "lon": 120.88},
        "Quezon City \u2192 Baliuag",
    )


def _live_segment_image(concept, image_url):
    assert concept == "container"
    return {
        "source": "sam-3.1",
        "concept": "container",
        "detections": [{"object_id": i} for i in range(7)],
    }


def test_snapshot_exposes_complete_scenario(monkeypatch):
    snap = _north_sea(monkeypatch)
    scenario = snap["scenario"]
    assert scenario["label"] == snap["label"]
    assert scenario["applicable"] == ["sea", "air", "road", "rail"]
    assert set(scenario["modes"]) == {"sea", "air", "road", "rail"}


def test_snapshot_scenario_marks_short_hop_modes(monkeypatch):
    snap = _short_hop(monkeypatch)
    assert snap["scenario"]["applicable"] == ["road", "rail"]
    assert {f["mode"] for f in snap["findings"]} == {"road", "rail"}
    assert set(snap["scenario"]["modes"]) == {"sea", "air", "road", "rail"}


def test_rank_corridor_modes_reproduces_snapshot(monkeypatch):
    snap = _north_sea(monkeypatch)
    scenario = snap["scenario"]
    again = orchestrator.rank_corridor_modes(
        scenario["modes"], snap["label"], scenario["applicable"]
    )
    assert again["ranked_options"] == snap["ranked_options"]
    assert again["findings"] == snap["findings"]
    assert again["fastest_alternative"] == snap["fastest_alternative"]


def test_summary_briefs_asked_corridor(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    snap = _north_sea(monkeypatch)
    body = orchestrator.run_demo_with_summary(snapshot=snap)
    assert body["label"] == snap["label"]
    assert body["synthetic"] is False
    assert body["ranked_options"] == snap["ranked_options"]
    assert body["summary"]["source"] == "deterministic"


def test_whatif_rescores_asked_corridor(monkeypatch):
    snap = _north_sea(monkeypatch)
    monkeypatch.setattr(
        wonder_client,
        "generate_whatif",
        lambda q, ranked, findings: {
            "source": "muse-wonder",
            "explanation": "road blocked",
            "assumptions": [
                {
                    "mode": "road",
                    "field": "delay_hours",
                    "delta": 30,
                    "reason": "test",
                }
            ],
        },
    )
    body = orchestrator.run_whatif("What if roads close?", snapshot=snap)
    assert body["label"] == snap["label"]
    assert body["synthetic"] is False
    assert body["ranked_baseline"] == snap["ranked_options"]
    assert {c["option_id"] for c in body["comparison"]} == {
        o["option_id"] for o in snap["ranked_options"]
    }
    road = next(f for f in body["findings_after"] if f["mode"] == "road")
    base_road = next(f for f in snap["findings"] if f["mode"] == "road")
    assert road["delay_hours"] == base_road["delay_hours"] + 30


def test_whatif_blank_question_rejected_for_corridor(monkeypatch):
    snap = _north_sea(monkeypatch)
    with pytest.raises(ValueError, match="What if"):
        orchestrator.run_whatif("   ", snapshot=snap)


def test_vision_unavailable_leaves_corridor_unchanged(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    snap = _north_sea(monkeypatch)
    body = orchestrator.run_demo_with_vision(snapshot=snap)
    assert body["vision"]["source"] == "unavailable"
    assert body["vision"]["sea_delay_added_hours"] == 0
    assert body["ranked_options"] == snap["ranked_options"]


def test_vision_blends_into_corridor_sea_leg(monkeypatch):
    monkeypatch.setattr(sam_client, "segment_image", _live_segment_image)
    snap = _north_sea(monkeypatch)
    base_delay = next(
        f for f in snap["findings"] if f["mode"] == "sea"
    )["delay_hours"]
    body = orchestrator.run_demo_with_vision(snapshot=snap)
    assert body["vision"]["sea_delay_added_hours"] == 8
    sea = next(f for f in body["findings"] if f["mode"] == "sea")
    assert sea["delay_hours"] == base_delay + 8
    assert "vision_adjustment" in sea
    assert snap["scenario"]["modes"]["sea"]["delay_hours"] == base_delay


def test_vision_short_hop_blends_zero(monkeypatch):
    monkeypatch.setattr(sam_client, "segment_image", _live_segment_image)
    snap = _short_hop(monkeypatch)
    body = orchestrator.run_demo_with_vision(snapshot=snap)
    assert body["vision"]["source"] == "sam-3.1"
    assert body["vision"]["sea_delay_added_hours"] == 0
    assert body["ranked_options"] == snap["ranked_options"]


def test_image_illustrates_asked_corridor(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    snap = _north_sea(monkeypatch)
    body = orchestrator.run_demo_with_image(snapshot=snap)
    assert body["label"] == snap["label"]
    assert body["synthetic"] is False
    assert body["image"]["source"] == "unavailable"
    assert body["ranked_options"] == snap["ranked_options"]


def test_challenge_mock_covers_asked_corridor(monkeypatch):
    snap = _north_sea(monkeypatch)
    body = orchestrator.run_challenge(["spark-open"], mock=True, snapshot=snap)
    assert body["label"] == snap["label"]
    assert body["synthetic"] is False
    assert [c["case_id"] for c in body["cases"]] == [
        "baseline",
        "sea-plus-12h",
        "air-plus-30h",
    ]
    assert all(r["source"] == "mock" for r in body["results"])
    assert all(r["schema_valid"] for r in body["results"])
    assert body["summary"][0]["cases"] == 3


def test_challenge_mock_short_hop_modes(monkeypatch):
    snap = _short_hop(monkeypatch)
    body = orchestrator.run_challenge(["glimmer"], mock=True, snapshot=snap)
    assert [c["case_id"] for c in body["cases"]] == [
        "baseline",
        "road-plus-12h",
        "rail-plus-30h",
    ]
    assert all(r["schema_valid"] for r in body["results"])


def test_summary_endpoint_accepts_corridor(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    _patch_live_layers(monkeypatch)
    body = north_sea_storm_summary(corridor="north-sea")
    assert body["synthetic"] is False
    assert len(body["ranked_options"]) == 4
    assert body["summary"]["source"] == "deterministic"


def test_summary_endpoint_defaults_to_incident(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    body = north_sea_storm_summary()
    assert body["synthetic"] is True
    assert "sea-wait" in {o["option_id"] for o in body["ranked_options"]}


def test_whatif_endpoint_accepts_places(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    snap = _north_sea(monkeypatch)
    monkeypatch.setattr(
        snapshot_mod, "snapshot_for_places", lambda o, d: snap
    )
    body = north_sea_storm_whatif(
        "What if sea closes?", from_place="Alpha", to="Beta"
    )
    assert body["label"] == snap["label"]
    assert {c["option_id"] for c in body["comparison"]} == {
        o["option_id"] for o in snap["ranked_options"]
    }


def test_whatif_endpoint_unknown_corridor_is_400():
    with pytest.raises(HTTPException) as exc_info:
        north_sea_storm_whatif("What if?", corridor="atlantis")
    assert exc_info.value.status_code == 400


def test_vision_endpoint_accepts_corridor(monkeypatch):
    monkeypatch.setattr(sam_client, "segment_image", _live_segment_image)
    _patch_live_layers(monkeypatch)
    body = north_sea_storm_vision(corridor="north-sea")
    assert body["synthetic"] is False
    assert body["vision"]["source"] == "sam-3.1"


def test_image_endpoint_accepts_corridor(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    _patch_live_layers(monkeypatch)
    body = north_sea_storm_image(corridor="north-sea")
    assert body["synthetic"] is False
    assert body["image"]["source"] == "unavailable"


def test_challenge_endpoint_accepts_corridor_mock(monkeypatch):
    _patch_live_layers(monkeypatch)
    body = north_sea_storm_challenge(
        models="spark-open", mock=True, corridor="north-sea"
    )
    assert body["synthetic"] is False
    assert len(body["cases"]) == 3
    assert all(r["schema_valid"] for r in body["results"])


def _routes_html():
    return routes_page.render_routes_page(orchestrator.run_demo())


def test_routes_declares_stage_basis_element():
    html = _routes_html()
    assert 'id="rt-stages-basis"' in html
    assert "AI analysis and evidence" in html
    assert "basis: North Sea incident" in html
    assert "<details" in html


def test_routes_hero_shows_fastest_and_why_it_wins():
    html = _routes_html()
    assert "rt-hero-fastest" in html
    assert "Fastest:" in html
    assert "Why it wins:" in html
    assert "rt-hero-why" in html
    script = html.split("<script>", 1)[1]
    assert "fastest_alternative" in script
    assert "top_reasons" in script


def test_routes_comparison_renders_cards():
    html = _routes_html()
    assert "Route comparison" in html
    assert 'id="rt-comp-list"' in html
    assert "<table" not in html.split("</details>", 1)[0].split("<body>", 1)[1]
    assert "opt-card" in html


def test_routes_ask_grounds_in_stage_basis():
    html = _routes_html()
    assert "rtStageQuery(true)" in html


def test_top_pick_reasons_name_margin_and_leads():
    demo = orchestrator.run_demo()
    reasons = orchestrator.top_pick_reasons(demo["ranked_options"])
    assert 1 <= len(reasons) <= 3
    assert reasons[-1].startswith("beats road-reroute by ")
    assert demo["top_reasons"] == reasons
    fastest = demo["fastest_alternative"]
    assert fastest["total_hours"] == round(
        fastest["transit_hours"] + fastest["delay_hours"], 1
    )


def test_routes_stages_follow_ask_context():
    html = _routes_html()
    assert "rtSetStagesBasis(snap)" in html
    assert "function rtStageParams()" in html
    assert html.count("rtStageQuery(false)") == 3
    # what-if fetch, bench fetch, and Ask grounding.
    assert html.count("rtStageQuery(true)") == 3


def test_routes_pill_handles_missing_sea():
    assert "SEA N/A" in _routes_html()


def test_routes_vision_reads_sea_by_mode():
    html = _routes_html()
    assert 'o.mode === "sea"' in html
    assert "no sea option on this corridor." in html


def test_routes_stages_use_two_balanced_columns():
    html = _routes_html()
    assert html.count('class="stage-col"') == 2
    markers = [
        "Evidence &mdash;",
        "Model Bench &mdash;",
        "What-if &mdash;",
        "Visual Brief &mdash;",
    ]
    positions = [html.index(marker) for marker in markers]
    assert positions == sorted(positions)
