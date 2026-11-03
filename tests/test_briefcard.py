"""Tests for the shareable incident briefing card (string checks, no browser)."""

from briefing_card import render_brief_card
from grid_page import render_grid_page
from main import north_sea_storm_brief_card
from orchestrator import run_demo


def _card():
    return render_brief_card(run_demo())


def test_card_is_deterministic():
    assert _card() == _card()


def test_card_leads_with_recommendation_and_tradeoff():
    html = _card()
    assert "incident brief" in html.lower()
    assert "rail-reroute" in html
    assert "Full-load intermodal rail via DE/DK/SE" in html
    assert "road-reroute" in html
    assert "saves $700" in html
    assert "saves 4h more" in html


def test_card_shows_impacts_and_ranking():
    html = _card()
    assert "sea" in html and "disrupted" in html
    assert "air-lift" in html
    assert "sea-wait" in html
    assert "Showing:" not in html


def test_illustration_lives_only_in_routes():
    from routes_page import render_routes_page

    assert "Generate illustration" not in _card()
    assert "/demo/north-sea-storm/image" not in _card()
    html = render_routes_page(run_demo())
    assert "Generate illustration" in html
    assert "illustrative only" in html.lower()


def test_card_has_no_illustration_section():
    html = _card()
    assert "AI-generated illustration" not in html
    assert "illus-btn" not in html
    assert "Ranking" in html
    assert "Impacts" in html


def test_card_is_dated_with_alternatives_and_fastest():
    html = _card()
    assert "Brief captured:" in html
    assert "brief-captured" in html
    assert "Alternatives, in order:" in html
    assert "road-reroute, air-lift, sea-wait" in html
    assert "brief-alts" in html
    assert "Fastest:" in html
    assert "brief-fastest" in html
    script = html.split("<script>", 1)[1]
    assert "toLocaleString()" in script
    assert "fastest_alternative" in script


def test_card_lists_sources_assumptions_and_labels():
    html = _card()
    assert "Evidence sources" in html
    assert "brief-sources" in html
    assert "Assumptions" in html
    assert "How to read the numbers" in html
    assert "always estimates" in html
    script = html.split("<script>", 1)[1]
    assert "snap.marine" in script
    assert "snap.rail" in script


def test_card_loads_live_values_on_open():
    html = _card()
    for target in (
        "brief-live-btn",
        "brief-live-note",
        "brief-rec-title",
        "brief-rec-nums",
        "brief-tradeoff",
        "brief-findings-body",
        "brief-ranking-body",
        "Refresh live values",
    ):
        assert target in html
    script = html.split("<script>", 1)[1]
    assert "async function briefLoadLive()" in script
    assert "\nbriefLoadLive();" in script
    assert script.count("/demo/north-sea-storm/live") == 1
    assert "innerHTML" not in script


def test_card_avoids_banned_framing_words():
    html = _card().lower()
    for word in ("dashboard", "command center", "control tower"):
        assert word not in html


def test_endpoint_returns_card_html():
    html = north_sea_storm_brief_card()
    assert "incident brief" in html.lower()
    assert "rail-reroute" in html
    assert "Recommendation" in html


def test_grid_page_links_to_brief_card():
    html = render_grid_page()
    assert 'href="/demo/north-sea-storm/brief-card"' in html
    assert "incident brief" in html.lower()
