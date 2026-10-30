"""Tests for the observable grid page (string checks, no browser)."""

from grid_page import render_grid_page

BANNED_WORDS = ["dashboard", "command center", "control tower"]


def test_page_calls_the_json_endpoints():
    html = render_grid_page()
    for path in (
        "/demo/north-sea-storm",
        "/demo/north-sea-storm/summary",
        "/demo/north-sea-storm/vision",
        "/demo/north-sea-storm/weather",
    ):
        assert path in html


def test_page_has_ranking_and_vision_beats():
    html = render_grid_page()
    assert "Ranked reroutes" in html
    assert "Run SAM verification" in html
    assert "muse-spark" in html
    assert "sam-3.1" in html


def test_page_avoids_banned_framing_words():
    html = render_grid_page().lower()
    for word in BANNED_WORDS:
        assert word not in html
