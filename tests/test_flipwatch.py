"""Flip-point analysis and flip watches: the boundary beside the pick."""

import pytest

import flipwatch
from flipwatch import (
    SCORING_FIELDS,
    create_watch,
    flip_analysis,
    format_flip,
    get_watch,
    incident_flip,
    list_watches,
    live_delay_observed,
    record_check,
    reset_watches,
    scan_flip,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_watches()
    yield
    reset_watches()


def _baseline():
    return incident_flip()


def test_baseline_flip_finds_rail_delay_boundary():
    flip = _baseline()["flip"]
    assert flip["top_option_id"] == "rail-reroute"
    assert flip["runner_up_option_id"] == "road-reroute"
    delays = [
        f for f in flip["flip_points"]
        if f["mode"] == "rail" and f["field"] == "delay_hours"
    ]
    assert len(delays) == 1
    found = delays[0]
    assert found["direction"] == 1
    assert found["new_top_id"] == "road-reroute"
    # Tighter than the challenge's +30h case: the computed boundary is the
    # first delta that flips, not a round-number guess.
    assert 0 < found["flip_delta"] <= 30


def test_baseline_flip_is_deterministic():
    assert _baseline()["flip"] == _baseline()["flip"]


def test_verdict_states_the_estimate_bet():
    verdict = _baseline()["flip"]["verdict"]
    assert "rail-reroute wins by" in verdict
    assert "rests on estimates" in verdict
    assert "road-reroute" in verdict
    assert "What would change it" in verdict


def test_held_probes_reported_not_hidden():
    flip = _baseline()["flip"]
    assert flip["held_without_flip"]
    for held in flip["held_without_flip"]:
        assert held["result"] == "no flip in range"
        assert held["mode"] in ("rail", "road")


def test_scan_flip_returns_none_when_range_holds():
    analysis = _baseline()["flip"]
    scenario_top = analysis["top_option_id"]
    import orchestrator

    scenario = orchestrator.load_scenario()
    baseline = scenario["baseline"]["storm_delay_hours_if_waiting"]

    def rerank(assumptions):
        updated = orchestrator.apply_whatif_assumptions(scenario, assumptions)
        findings = orchestrator.collect_findings(updated)
        return orchestrator.score_options(
            orchestrator.build_options(findings, baseline)
        )

    # One 5% cost step cannot close the margin: honest None, not a guess.
    assert (
        scan_flip(rerank, scenario_top, "rail", "cost_usd", 3800, 1, 190, 1)
        is None
    )


def test_format_flip_lines():
    delay = {
        "mode": "rail",
        "field": "delay_hours",
        "start_value": 6,
        "flip_value": 11,
        "flip_delta": 5,
        "new_top_id": "road-reroute",
    }
    assert format_flip(delay) == (
        "rail delay +5h (6h to 11h) flips the pick to road-reroute"
    )
    cost = {
        "mode": "rail",
        "field": "cost_usd",
        "start_value": 3800,
        "flip_value": 4940,
        "flip_delta": 1140,
        "new_top_id": "road-reroute",
    }
    assert format_flip(cost) == (
        "rail cost +1,140 ($3,800 to $4,940) flips the pick to road-reroute"
    )


def test_backing_fails_closed_on_unknown_provenance():
    backing = flipwatch._backing({"rail": {"delay_hours": "measured"}}, "rail")
    assert backing["strong"] == ["delay_hours"]
    # Missing fields read as unknown, and unknown is weak — never trusted.
    assert backing["weak"] == ["cost_usd", "on_time_probability", "confidence"]


def test_verdict_confesses_estimate_vs_live_split():
    top = {"option_id": "rail-reroute", "mode": "rail"}
    runner = {"option_id": "road-reroute", "mode": "road"}
    bet = {
        "top_backing": {
            "strong": [],
            "medium": [],
            "weak": ["delay_hours", "cost_usd"],
        },
        "runner_up_backing": {
            "strong": ["delay_hours"],
            "medium": [],
            "weak": ["cost_usd"],
        },
    }
    verdict = flipwatch._verdict(top, runner, 0.0848, bet, [])
    assert "rests on estimates (rail delay hours and cost)" in verdict
    assert "road-reroute's delay hours is grounded in live data" in verdict


def test_live_delay_observed_reads_scenario_slices():
    scenario = {
        "modes": {
            mode: {"delay_hours": hours}
            for mode, hours in (
                ("sea", 2),
                ("air", 4),
                ("road", 6),
                ("rail", 8),
            )
        }
    }
    assert live_delay_observed(scenario) == {
        "sea": 2,
        "air": 4,
        "road": 6,
        "rail": 8,
    }


def _watched():
    analysis = _baseline()["flip"]
    return create_watch(
        "demo",
        analysis,
        {"sea": 48, "air": 8, "road": 6, "rail": 6},
    )


def test_watch_holds_at_start_values():
    watch = _watched()
    assert watch["watch_id"] == "watch-1"
    assert watch["persistent"] is False
    assert watch["checks"] == 0
    record_check(
        watch, {"sea": 48, "air": 8, "road": 6, "rail": 6}
    )
    assert watch["checks"] == 1
    assert watch["last_status"] == "holding"
    live = [t for t in watch["thresholds"] if t["live"]]
    assert live and all(t["status"] == "holding" for t in live)
    static = [t for t in watch["thresholds"] if not t["live"]]
    assert static and all(
        t["status"] == "static-holding" for t in static
    )


def test_watch_goes_near_then_flipped():
    watch = _watched()
    rail_delay = next(
        t for t in watch["thresholds"]
        if t["live"] and t["mode"] == "rail"
    )
    start, flip = rail_delay["start_value"], rail_delay["flip_value"]
    near_value = flip - max(1, int((flip - start) * 0.25))
    assert start < near_value < flip
    record_check(
        watch, {"sea": 48, "air": 8, "road": 6, "rail": near_value}
    )
    assert rail_delay["status"] == "near"
    assert watch["last_status"] == "near"
    record_check(watch, {"sea": 48, "air": 8, "road": 6, "rail": flip})
    assert rail_delay["status"] == "crossed"
    assert rail_delay["observed"] == flip
    assert watch["last_status"] == "flipped"
    assert watch["checks"] == 2


def test_watch_registry_lists_in_creation_order():
    analysis = _baseline()["flip"]
    first = create_watch("a", analysis, {})
    second = create_watch("b", analysis, {})
    assert [w["watch_id"] for w in list_watches()] == [
        first["watch_id"],
        second["watch_id"],
    ]
    assert get_watch(first["watch_id"]) is first
    assert get_watch("watch-999") is None


def test_flip_endpoint_serves_baseline_without_network():
    from main import north_sea_storm_flip

    body = north_sea_storm_flip(live=False)
    assert body["data_mode"] == "baseline"
    assert body["flip"]["top_option_id"] == "rail-reroute"
    assert body["flip"]["verdict"]
    assert set(body["provenance"]) == {"sea", "air", "road", "rail"}


def test_check_unknown_watch_is_404_without_network():
    import pytest
    from fastapi import HTTPException

    from main import check_flip_watch

    with pytest.raises(HTTPException) as exc_info:
        check_flip_watch("watch-999")
    assert exc_info.value.status_code == 404


def test_grid_flip_section_avoids_banned_framing():
    from grid_page import render_grid_page

    html = render_grid_page()
    assert "flip-watch" in html
    lowered = html.lower()
    for word in ("dashboard", "command center", "control tower", "console"):
        assert word not in lowered
