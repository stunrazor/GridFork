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


def test_card_shows_impacts_ranking_and_synthetic_label():
    html = _card()
    assert "sea" in html and "disrupted" in html
    assert "air-lift" in html
    assert "sea-wait" in html
    assert "SYNTHETIC DATA" in html


def test_card_labels_illustration_as_illustrative_not_evidence():
    html = _card()
    assert "Generate illustration" in html
    assert "AI-generated illustration" in html
    lowered = html.lower()
    assert "illustrative only" in lowered
    assert "not a real port image" in lowered
    assert "sam" in lowered


def test_card_generates_illustration_on_demand_only():
    html = _card()
    assert "/demo/north-sea-storm/image" in html
    script = html.split("<script>", 1)[1]
    assert script.count("/demo/north-sea-storm/image") == 1
    assert "addEventListener" in script


def test_card_avoids_banned_framing_words():
    html = _card().lower()
    for word in ("dashboard", "command center", "control tower"):
        assert word not in html


def test_endpoint_returns_card_html():
    html = north_sea_storm_brief_card()
    assert "incident brief" in html.lower()
    assert "rail-reroute" in html
    assert "Generate illustration" in html


def test_grid_page_links_to_brief_card():
    html = render_grid_page()
    assert 'href="/demo/north-sea-storm/brief-card"' in html
    assert "incident brief" in html.lower()
